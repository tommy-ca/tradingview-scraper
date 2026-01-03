import fcntl
import hashlib
import json
import logging
import os
import shutil
import tempfile
from datetime import datetime
from typing import Any, Dict, List, Optional, cast

import numpy as np
import pandas as pd

from tradingview_scraper.selection_engines import SelectionRequest, SelectionResponse, build_selection_engine
from tradingview_scraper.settings import get_settings
from tradingview_scraper.utils.audit import AuditLedger, get_df_hash  # type: ignore

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("natural_selection")

AUDIT_FILE = "data/lakehouse/selection_audit.json"


def run_selection(
    returns: pd.DataFrame,
    raw_candidates: List[Dict[str, Any]],
    stats_df: Optional[pd.DataFrame] = None,
    top_n: int = 2,
    threshold: float = 0.5,
    max_clusters: int = 25,
    m_gate: float = 0.0,
    mode: Optional[str] = None,
) -> SelectionResponse:
    """Orchestrates selection using the modular engine system."""
    settings = get_settings()
    engine_name = mode or settings.features.selection_mode
    engine = build_selection_engine(engine_name)
    request = SelectionRequest(
        top_n=top_n,
        threshold=threshold,
        max_clusters=max_clusters,
        min_momentum_score=m_gate,
    )
    response = engine.select(returns, raw_candidates, stats_df, request)
    for warning in response.warnings:
        logger.warning(warning)
    return response


def natural_selection(
    returns_path: str = "data/lakehouse/portfolio_returns.pkl",
    meta_path: str = "data/lakehouse/portfolio_candidates_raw.json",
    stats_path: str = "data/lakehouse/antifragility_stats.json",
    output_path: str = "data/lakehouse/portfolio_candidates.json",
    top_n_per_cluster: Optional[int] = None,
    dist_threshold: Optional[float] = None,
    max_clusters: int = 25,
    min_momentum_score: Optional[float] = None,
    mode: Optional[str] = None,
):
    settings = get_settings()
    top_n = top_n_per_cluster if top_n_per_cluster is not None else settings.top_n
    threshold = dist_threshold if dist_threshold is not None else settings.threshold
    m_gate = min_momentum_score if min_momentum_score is not None else settings.min_momentum_score

    run_dir = settings.prepare_summaries_run_dir()
    ledger = AuditLedger(run_dir) if settings.features.feat_audit_ledger else None

    if not os.path.exists(returns_path) or not os.path.exists(meta_path):
        logger.error("Data missing.")
        return

    returns = cast(pd.DataFrame, pd.read_pickle(returns_path))
    with open(meta_path, "r") as f_meta:
        raw_candidates = json.load(f_meta)
    stats_df = pd.read_json(stats_path).set_index("Symbol") if os.path.exists(stats_path) else None

    meta_hash = hashlib.sha256(json.dumps(raw_candidates, sort_keys=True).encode()).hexdigest()

    if ledger:
        if not ledger.last_hash:
            manifest_hash = hashlib.sha256(open(settings.manifest_path, "rb").read()).hexdigest() if settings.manifest_path.exists() else "unknown"
            ledger.record_genesis(settings.run_id, settings.profile, manifest_hash)

        ledger.record_intent(
            step="natural_selection",
            params={"top_n": top_n, "threshold": threshold, "mode": mode},
            input_hashes={"returns": get_df_hash(returns), "candidates_raw": meta_hash, "stats": get_df_hash(stats_df) if stats_df is not None else "none"},
        )

    response = run_selection(returns, raw_candidates, stats_df, top_n, threshold, max_clusters, m_gate, mode=mode)
    winners = response.winners
    audit_clusters = response.audit_clusters
    spec_version = response.spec_version
    vetoes = response.vetoes
    engine_metrics = response.metrics

    # Atomic write for winners
    with tempfile.NamedTemporaryFile("w", dir=os.path.dirname(output_path), delete=False) as tf:
        json.dump(winners, tf, indent=2)
        temp_name = tf.name
    os.replace(temp_name, output_path)

    def _sanitize(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {str(k): _sanitize(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_sanitize(x) for x in obj]
        if hasattr(obj, "to_dict"):
            return obj.to_dict()
        if isinstance(obj, (np.integer, np.floating)):
            return obj.item()
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return obj

    sanitized_metrics = cast(Dict[str, Any], _sanitize(engine_metrics))

    # Update Audit File with selection info (Atomic + Locked)
    settings = get_settings()
    run_audit_file = settings.run_config_dir / "selection_audit.json"
    run_audit_file.parent.mkdir(parents=True, exist_ok=True)
    lock_file = str(run_audit_file) + ".lock"
    try:
        with open(lock_file, "w") as lf:
            fcntl.flock(lf, fcntl.LOCK_EX)
            audit_data = {}
            # Base data from shared lakehouse audit
            if os.path.exists(AUDIT_FILE):
                try:
                    with open(AUDIT_FILE, "r") as f:
                        content = f.read().strip()
                        if content:
                            audit_data = json.loads(content)
                except Exception:
                    pass

            audit_data["selection"] = {
                "timestamp": datetime.now().isoformat(),
                "total_raw_symbols": len(raw_candidates),
                "total_selected": len(winners),
                "lookbacks_used": [60, 120, 200],
                "clusters": {str(k): v for k, v in audit_clusters.items()},
                "spec_version": spec_version,
                "vetoes": vetoes,
                "metrics": sanitized_metrics,
            }

            # Write to run directory audit
            with tempfile.NamedTemporaryFile("w", dir=os.path.dirname(run_audit_file), delete=False) as tf:
                json.dump(audit_data, tf, indent=2)
                temp_name = tf.name
            os.replace(temp_name, run_audit_file)

            # Update shared lakehouse audit
            os.makedirs(os.path.dirname(AUDIT_FILE), exist_ok=True)
            with tempfile.NamedTemporaryFile("w", dir=os.path.dirname(AUDIT_FILE), delete=False) as tf:
                json.dump(audit_data, tf, indent=2)
                temp_name = tf.name
            os.replace(temp_name, AUDIT_FILE)

            # ALSO: Copy to run-specific directory for provenance
            run_audit = run_dir / "selection_audit.json"
            shutil.copy2(AUDIT_FILE, run_audit)

            fcntl.flock(lf, fcntl.LOCK_UN)
    except Exception as e:
        logger.warning(f"Could not update audit file: {e}")

    selection_audit_hash = None
    if os.path.exists(run_dir / "selection_audit.json"):
        selection_audit_hash = hashlib.sha256((run_dir / "selection_audit.json").read_bytes()).hexdigest()

    if ledger:
        audit_payload = cast(
            Dict[str, Any],
            _sanitize(
                {
                    "selection": {
                        "total_raw_symbols": len(returns.columns),
                        "total_selected": len(winners),
                        "clusters": audit_clusters,
                        "mode": mode,
                        "spec_version": spec_version,
                        "vetoes": vetoes,
                        "engine_metrics": sanitized_metrics,
                    },
                    "portfolio_clusters": {str(c): d["selected"] for c, d in audit_clusters.items()},
                    "winner_metadata": {w["symbol"]: {k: w.get(k) for k in ["exchange", "sector", "industry", "type", "identity"]} for w in winners},
                }
            ),
        )
        ledger_metrics: Dict[str, Any] = {
            "n_winners": len(winners),
            "n_vetoes": len(vetoes),
            "spec_version": spec_version,
            "raw_pool_count": len(returns.columns),
            "selected_count": len(winners),
        }
        if isinstance(sanitized_metrics, dict):
            ledger_metrics.update(sanitized_metrics)
        ledger.record_outcome(
            step="natural_selection",
            status="success",
            output_hashes={
                "candidates": hashlib.sha256(json.dumps(winners).encode()).hexdigest(),
                "candidates_raw": meta_hash,
                "selection_audit": selection_audit_hash or "unknown",
            },
            metrics=ledger_metrics,
            data=audit_payload,
        )

    logger.info(f"Natural Selection Complete ({mode or 'default'}): {len(winners)} candidates.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--top-n", type=int)
    parser.add_argument("--threshold", type=float)
    parser.add_argument("--max-clusters", type=int, default=25)
    parser.add_argument("--min-momentum", type=float)
    parser.add_argument("--mode", type=str, choices=["v2.0", "v2", "v2.1", "v3", "v3.1", "v3.2", "legacy"], help="Selection spec version")
    args = parser.parse_args()
    natural_selection(top_n_per_cluster=args.top_n, dist_threshold=args.threshold, max_clusters=args.max_clusters, min_momentum_score=args.min_momentum, mode=args.mode)
