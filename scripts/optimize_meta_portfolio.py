import argparse
import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional, cast

import pandas as pd

sys.path.append(os.getcwd())
from tradingview_scraper.portfolio_engines import build_engine
from tradingview_scraper.portfolio_engines.base import EngineRequest, ProfileName
from tradingview_scraper.settings import get_settings
from tradingview_scraper.utils.audit import AuditLedger, get_df_hash

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("optimize_meta_portfolio")


def optimize_meta(returns_path: str, output_path: str, profile: Optional[str] = None, meta_profile: Optional[str] = None):
    settings = get_settings()
    run_dir = settings.prepare_summaries_run_dir()
    ledger = AuditLedger(run_dir) if settings.features.feat_audit_ledger else None

    # Resolve Meta Profile from settings if not passed
    m_prof = meta_profile or os.getenv("PROFILE") or "meta_production"

    # Handle Profile Matrix
    if profile is None:
        # CR-831: Workspace Isolation - Infer base directory from returns_path
        input_path = Path(returns_path)
        base_dir = input_path.parent if input_path.is_file() else input_path

        # Search for all meta_returns_{meta_profile}_*.pkl in the resolved directory
        files = list(base_dir.glob(f"meta_returns_{m_prof}_*.pkl"))

        # If none found in run dir, try lakehouse (Legacy fallback)
        if not files:
            files = list(Path("data/lakehouse").glob(f"meta_returns_{m_prof}_*.pkl"))

        # Global fallback to old pattern if no profile-specific ones found
        if not files:
            files = list(base_dir.glob("meta_returns_*.pkl"))
            if not files:
                files = list(Path("data/lakehouse").glob("meta_returns_*.pkl"))

        if not files and input_path.exists() and input_path.is_file():
            files = [input_path]
    else:
        # Try run_dir first, then lakehouse
        input_path = Path(returns_path)
        base_dir = input_path.parent if input_path.is_file() else input_path

        candidates = [
            base_dir / f"meta_returns_{m_prof}_{profile}.pkl",
            Path("data/lakehouse") / f"meta_returns_{m_prof}_{profile}.pkl",
            base_dir / f"meta_returns_{profile}.pkl",
            Path("data/lakehouse") / f"meta_returns_{profile}.pkl",
        ]
        files = [c for c in candidates if c.exists()]

    for p_path in files:
        if not p_path.exists():
            continue

        # Extract profile from filename: meta_returns_{m_prof}_<prof>.pkl or meta_returns_<prof>.pkl
        stem = p_path.stem
        if f"meta_returns_{m_prof}_" in stem:
            prof_name = stem.replace(f"meta_returns_{m_prof}_", "")
        else:
            prof_name = stem.replace("meta_returns_", "")

        if prof_name == "meta_returns":
            prof_name = "hrp"  # Default legacy

        # Map profile to valid ProfileName
        target_profile: ProfileName = "hrp"
        try:
            target_profile = cast(ProfileName, prof_name)
        except Exception:
            pass

        logger.info(f"🔨 Fractal Meta-Optimization ({m_prof}): {target_profile}")

        meta_rets = pd.read_pickle(p_path)
        if not isinstance(meta_rets, pd.DataFrame):
            meta_rets = pd.DataFrame(meta_rets)

        if meta_rets.empty:
            continue

        clusters = {str(col): [str(col)] for col in meta_rets.columns}

        if ledger:
            ledger.record_intent(
                step=f"meta_optimize_{target_profile}",
                params={"engine": "custom", "profile": str(target_profile), "n_sleeves": len(meta_rets.columns)},
                input_hashes={"meta_returns": get_df_hash(meta_rets)},
                context={"meta_profile": m_prof},
            )

        engine = build_engine("custom")
        request = EngineRequest(profile=target_profile, engine="custom", cluster_cap=1.0)

        try:
            # Explicitly cast to satisfy static analyzer
            rets_df = cast(pd.DataFrame, meta_rets)

            # If barbell is requested, we need antifragility stats for the sleeves
            current_stats = pd.DataFrame()
            if target_profile == "barbell":
                from tradingview_scraper.risk import AntifragilityAuditor

                auditor = AntifragilityAuditor()
                af_df = auditor.audit(rets_df)
                current_stats = af_df

            response = engine.optimize(returns=rets_df, clusters=clusters, meta={}, stats=current_stats, request=request)
            weights_df = response.weights
            if weights_df.empty:
                continue

            # Save specific matrix result
            p_output_path = Path(output_path).parent / f"meta_optimized_{m_prof}_{target_profile}.json"

            artifact = {
                "metadata": {
                    "source": str(p_path),
                    "meta_profile": m_prof,
                    "engine": "custom",
                    "profile": target_profile,
                    "n_sleeves": len(meta_rets.columns),
                    "run_id": settings.run_id,
                    "generated_at": str(pd.Timestamp.now()),
                },
                "weights": weights_df.to_dict(orient="records"),
            }

            os.makedirs(os.path.dirname(p_output_path), exist_ok=True)
            with open(p_output_path, "w") as f:
                json.dump(artifact, f, indent=2)

            logger.info(f"✅ Meta-optimized weights ({m_prof}/{target_profile}) saved to {p_output_path}")

        except Exception as e:
            logger.error(f"Meta-optimization failed for {target_profile}: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--returns", default="data/lakehouse/meta_returns.pkl")
    parser.add_argument("--output", default="data/lakehouse/meta_optimized.json")
    parser.add_argument("--profile", help="Specific risk profile to optimize (e.g. hrp)")
    parser.add_argument("--meta-profile", help="Meta profile name (e.g. meta_super_benchmark)")
    args = parser.parse_args()

    optimize_meta(args.returns, args.output, args.profile, args.meta_profile)
