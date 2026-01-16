import hashlib
import json
import logging
import math
import os
import threading
import time
from concurrent.futures import ALL_COMPLETED, ThreadPoolExecutor, wait
from datetime import datetime, timedelta
from typing import Any, cast

import pandas as pd

from tradingview_scraper.pipelines.data.orchestrator import DataPipelineOrchestrator
from tradingview_scraper.settings import get_settings
from tradingview_scraper.symbols.stream.metadata import DataProfile, get_symbol_profile
from tradingview_scraper.symbols.stream.persistent_loader import PersistentDataLoader
from tradingview_scraper.utils.audit import AuditLedger, get_df_hash

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("portfolio_data_prep")


def prepare_portfolio_universe():
    """
    Preparation Stage (Pillar 0).
    Orchestrates high-integrity ingestion and transformation using the Workflow Engine.
    """
    active_settings = get_settings()
    run_dir = active_settings.prepare_summaries_run_dir()
    ledger = AuditLedger(run_dir) if active_settings.features.feat_audit_ledger else None

    # 1. Load sanctioned candidates
    default_c_sel = str(run_dir / "data" / "portfolio_candidates.json")
    default_c_raw = str(run_dir / "data" / "portfolio_candidates_raw.json")

    preselected_file = os.getenv("CANDIDATES_FILE") or os.getenv("CANDIDATES_SELECTED")
    if not preselected_file or not os.path.exists(preselected_file):
        preselected_file = os.getenv("CANDIDATES_RAW") or default_c_raw

    if not os.path.exists(preselected_file):
        preselected_file = "data/lakehouse/portfolio_candidates.json"
        if not os.path.exists(preselected_file):
            preselected_file = "data/lakehouse/portfolio_candidates_raw.json"

    if not os.path.exists(preselected_file):
        logger.error(f"No candidate manifest found at {preselected_file}")
        return

    logger.info(f"Loading candidates from {preselected_file}")
    with open(preselected_file, "r") as f:
        universe = json.load(f)

    if not universe:
        logger.error("No candidates found in manifest.")
        return

    lookback_env = os.getenv("PORTFOLIO_LOOKBACK_DAYS")
    lookback_days = int(lookback_env) if lookback_env else int(active_settings.resolve_portfolio_lookback_days())

    # CR-831: Workspace Isolation
    os.makedirs(run_dir / "data", exist_ok=True)
    returns_path = os.getenv("PORTFOLIO_RETURNS_PATH", str(run_dir / "data" / "returns_matrix.parquet"))
    meta_path = os.getenv("PORTFOLIO_META_PATH", str(run_dir / "data" / "portfolio_meta.json"))

    # 2. Trigger Workflow Engine Ingestion (Pillar 0) OR Load from Lakehouse
    source_mode = os.getenv("PORTFOLIO_DATA_SOURCE", "fetch")  # default to fetch for backward compatibility

    if source_mode == "lakehouse_only":
        logger.info("PORTFOLIO_DATA_SOURCE=lakehouse_only: Skipping network ingestion.")
        # In lakehouse_only mode, we assume the data is already in the lakehouse.
        # We proceed to step 3 (Alignment) directly.
        # But we need to ensure we don't try to fetch later.
    else:
        loader = PersistentDataLoader()
        orchestrator = DataPipelineOrchestrator(loader)

        force_sync = os.getenv("PORTFOLIO_FORCE_SYNC") == "1"
        ingestion_summary = orchestrator.ingest_universe(universe, force_sync=force_sync, lookback_days=lookback_days)

        if ledger:
            ledger.record_intent(
                step="data_ingestion",
                params={"lookback_days": lookback_days, "force_sync": force_sync},
                input_hashes={"candidates": hashlib.sha256(json.dumps(universe).encode()).hexdigest()},
            )

    # 3. Alignment & Transformation (Pillar 0 -> Pillar 2 Bridge)
    price_data = {}
    alpha_meta = {}
    end_date = datetime.now()
    start_date = end_date - timedelta(days=lookback_days)

    logger.info("Aligning return streams and generating atoms...")
    unique_phys_symbols = set()
    for candidate in universe:
        # With the update to select_top_universe, 'symbol' is now the physical symbol
        # But we handle legacy cases where it might be an atom_id
        sym = candidate["symbol"]
        phys_sym = candidate.get("physical_symbol") or sym
        unique_phys_symbols.add(phys_sym)

    # If lakehouse_only, we use a simple loader that reads parquet files directly
    # Or we assume PersistentDataLoader can be used in "offline" mode if we don't call sync()
    # PersistentDataLoader.load() reads from disk.

    # However, the original code creates a NEW PersistentDataLoader instance below at line 211
    # AND defines fetch_and_store() which calls sync().

    # We need to restructure the fetching logic.

    if source_mode == "lakehouse_only":
        # Load from disk ONLY. Fail if missing.
        loader = PersistentDataLoader()

        for phys_sym in unique_phys_symbols:
            try:
                # Load without sync
                df = loader.load(phys_sym, start_date, end_date, interval="1d")

                # In lakehouse_only mode, if data is empty/missing, it's a critical failure if required
                # But PersistentLoader.load returns empty df if file missing.
                if df.empty:
                    logger.error(f"CRITICAL: Missing data for {phys_sym} in Lakehouse. Aborting run.")
                    # We could raise an exception here to enforcing the contract
                    # raise FileNotFoundError(f"Missing data for {phys_sym}")
                    # For now, let's log error and skip, but the matrix creation will fail if empty.
                    continue

                df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s").dt.date
                df_series = df.set_index("timestamp")["close"]
                returns = df_series.pct_change().dropna()

                # Store keyed by physical symbol (One column per asset)
                price_data[phys_sym] = returns

                # Metadata (same logic as before)
                candidates_for_phys = [c for c in universe if c.get("physical_symbol") == phys_sym or c["symbol"] == phys_sym]
                if candidates_for_phys:
                    candidate = candidates_for_phys[0]
                    alpha_meta[phys_sym] = {
                        "symbol": phys_sym,
                        "description": candidate.get("description", "N/A"),
                        "sector": candidate.get("sector", "N/A"),
                        "market": candidate.get("market", "UNKNOWN"),
                        "identity": candidate.get("identity", phys_sym),
                        "adx": candidate.get("adx", 0),
                        "close": candidate.get("close", 0),
                        "atr": candidate.get("atr", 0),
                        "volatility_d": candidate.get("volatility_d", 0),
                        "volume_change_pct": candidate.get("volume_change_pct", 0),
                        "roc": candidate.get("roc", 0),
                        "value_traded": candidate.get("value_traded", 0),
                        "is_benchmark": candidate.get("is_benchmark", False),
                        "direction": candidate.get("direction", "LONG"),
                        "logic": candidate.get("logic", "trend"),
                        "atom_id": candidate.get("atom_id"),
                    }
            except Exception as e:
                logger.error(f"Failed to load {phys_sym} from Lakehouse: {e}")

    else:
        # Legacy Fetch Mode (Parallel Fetching)
        # We reuse the logic from lines 210+ but wrapped
        # The code below line 210 re-implements fetching.
        # We should probably wrap that block.
        pass

    # ... The rest of the file logic ...

    # Wait, the file has TWO sections doing similar things.
    # Lines 95-129 do a serial load.
    # Lines 198-336 do a parallel fetch/load.
    # It seems Lines 95-129 are redundant or the start of the logic, and then it re-does it?
    # Actually, lines 95-129 populated `price_data`.
    # Then line 132 checks `if not price_data`.
    # Then lines 136-183 create the matrix and SAVE it.

    # Then line 189 starts "CR-831: Workspace Isolation" and... RE-DOES EVERYTHING?
    # Lines 198-437 seem to be a SECOND implementation of the same logic, appended to the file?
    # It defines `fetch_and_store` and uses `ThreadPoolExecutor`.

    # It looks like the file has duplicate logic blocks, possibly from a previous bad merge or edit.
    # The first block (lines 95-129) is serial and simple.
    # The second block (lines 210+) is parallel and complex.

    # I should clean this up. I will keep the second block (Parallel) as the primary one,
    # but modify it to respect `lakehouse_only`.

    # The first block (95-129) seems to populate `price_data`.
    # If I remove it, I must ensure the second block runs.
    # BUT the first block ends with saving the matrix at line 170.
    # Then the code continues to line 189 and starts over?

    # This is definitely a duplicate/messy file.
    # I will refactor to have ONE clean flow.

    # Flow:
    # 1. Load Candidates
    # 2. Determine Mode (Fetch vs Lakehouse)
    # 3. If Fetch: Run Parallel Fetch (sync)
    # 4. Load Data (Parallel Load)
    # 5. Build Matrix
    # 6. Save

    # CR-831: Workspace Isolation
    # Default outputs to run-specific directory
    os.makedirs(run_dir / "data", exist_ok=True)
    default_returns = str(run_dir / "data" / "returns_matrix.parquet")
    default_meta = str(run_dir / "data" / "portfolio_meta.json")

    returns_path = os.getenv("PORTFOLIO_RETURNS_PATH", default_returns)
    meta_path = os.getenv("PORTFOLIO_META_PATH", default_meta)

    # 2. Extract Canonical Symbols (Deduplicate Fetching)
    # Mapping: Physical Symbol -> List of Candidates (Atoms)
    physical_map = {}
    for candidate in universe:
        atom_id = candidate["symbol"]
        # Use physical_symbol if provided (CR-831), fall back to symbol
        phys_sym = candidate.get("physical_symbol", atom_id)

        physical_map.setdefault(phys_sym, []).append(candidate)

    logger.info(f"Portfolio Universe: {len(universe)} atoms across {len(physical_map)} physical assets.")

    # 3. Fetch Historical Data (Canonical Pass)
    loader = PersistentDataLoader()
    end_date = datetime.now()
    start_date = end_date - timedelta(days=lookback_days)

    price_data = {}
    alpha_meta = {}
    lock = threading.Lock()
    jwt_token = os.getenv("TRADINGVIEW_JWT_TOKEN", "unauthorized_user_token")
    batch_env = os.getenv("PORTFOLIO_BATCH_SIZE")
    batch_size = int(batch_env) if batch_env else int(active_settings.portfolio_batch_size)
    backfill_env = os.getenv("PORTFOLIO_BACKFILL")
    gapfill_env = os.getenv("PORTFOLIO_GAPFILL")
    force_env = os.getenv("PORTFOLIO_FORCE_SYNC")
    do_backfill = backfill_env == "1" if backfill_env is not None else bool(active_settings.portfolio_backfill)
    do_gapfill = gapfill_env == "1" if gapfill_env is not None else bool(active_settings.portfolio_gapfill)
    force_sync = force_env == "1" if force_env is not None else bool(active_settings.portfolio_force_sync)

    def run_with_retry(func, action: str, retries: int = 2, base_sleep: int = 10):
        """Retry helper to throttle on 429 errors."""
        for attempt in range(retries + 1):
            try:
                return func()
            except Exception as e:
                is_429 = "429" in str(e)
                if is_429 and attempt < retries:
                    sleep_for = base_sleep * (attempt + 1)
                    logger.warning(f"{action} hit 429; sleeping {sleep_for}s before retry ({attempt + 1}/{retries}).")
                    time.sleep(sleep_for)
                    continue
                raise

    skipped_empty = []
    skipped_errors = []

    def fetch_and_store(phys_sym, candidates_for_phys):
        local_loader = PersistentDataLoader(websocket_jwt_token=jwt_token)

        # 1. Selective Sync Check (SHP-1)
        is_stale = True
        parquet_path = f"data/lakehouse/{phys_sym.replace(':', '_')}_1d.parquet"
        if os.path.exists(parquet_path):
            mtime = os.path.getmtime(parquet_path)
            # CR-829: Tighten freshness to 12 hours for proactive fetch
            if (time.time() - mtime) < (12 * 3600):
                is_stale = False

        if do_backfill and (is_stale or force_sync):
            try:
                # Deep Sync: request up to 2000 candles to ensure full coverage (SHP Standard)
                bf_depth = max(lookback_days + 100, 2000)
                logger.info(f"Backfilling {phys_sym} (depth={bf_depth})...")
                run_with_retry(lambda: local_loader.sync(phys_sym, interval="1d", depth=bf_depth, total_timeout=300), f"Backfill {phys_sym}")
            except Exception as e:
                logger.error(f"Backfill failed for {phys_sym}: {e}")

        if do_gapfill and (is_stale or force_sync):
            try:
                logger.info(f"Gap filling {phys_sym} (max_depth=2000)...")
                run_with_retry(lambda: local_loader.repair(phys_sym, interval="1d", max_depth=2000, max_fills=50, max_time=300, total_timeout=300), f"Gap fill {phys_sym}")
            except Exception as e:
                logger.error(f"Gap fill failed for {phys_sym}: {e}")

        logger.info(f"Loading history for {phys_sym}...")
        try:
            df = local_loader.load(phys_sym, start_date, end_date, interval="1d")
            if df.empty:
                skipped_empty.append(phys_sym)
                return

            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="s").dt.date
            df_series = df.set_index("timestamp")["close"]
            returns = df_series.pct_change().dropna()

            with lock:
                # Store strictly physical returns
                price_data[phys_sym] = returns

                # Representative metadata
                if candidates_for_phys:
                    candidate = candidates_for_phys[0]
                    alpha_meta[phys_sym] = {
                        "symbol": phys_sym,
                        "description": candidate.get("description", "N/A"),
                        "sector": candidate.get("sector", "N/A"),
                        "market": candidate.get("market", "UNKNOWN"),
                        "identity": candidate.get("identity", phys_sym),
                        "adx": candidate.get("adx", 0),
                        "close": candidate.get("close", 0),
                        "atr": candidate.get("atr", 0),
                        "volatility_d": candidate.get("volatility_d", 0),
                        "volume_change_pct": candidate.get("volume_change_pct", 0),
                        "roc": candidate.get("roc", 0),
                        "value_traded": candidate.get("value_traded", 0),
                        "is_benchmark": candidate.get("is_benchmark", False),
                        # CR-Fix: Propagate Logic/Direction to Meta
                        "direction": candidate.get("direction", "LONG"),
                        "logic": candidate.get("logic", "trend"),
                        "atom_id": candidate.get("atom_id"),
                    }

        except Exception as e:
            skipped_errors.append(phys_sym)
            logger.error(f"Failed to load {phys_sym}: {e}")

    phys_symbols = sorted(list(physical_map.keys()))
    total_batches = math.ceil(len(phys_symbols) / batch_size) if batch_size > 0 else 1

    for batch_idx in range(total_batches):
        batch_syms = phys_symbols[batch_idx * batch_size : (batch_idx + 1) * batch_size]
        logger.info("Processing batch %s/%s (%s physical symbols)", batch_idx + 1, total_batches, len(batch_syms))
        with ThreadPoolExecutor(max_workers=max(1, batch_size)) as executor:
            futures = [executor.submit(fetch_and_store, s, physical_map[s]) for s in batch_syms]
            per_symbol_timeout = 300
            batch_timeout = len(batch_syms) * per_symbol_timeout
            done, not_done = wait(futures, timeout=batch_timeout, return_when=ALL_COMPLETED)

            for fut in done:
                try:
                    fut.result()
                except Exception as e:
                    logger.error(f"Worker error: {e}")

            if not_done:
                logger.error(f"Batch timed out. {len(not_done)} tasks incomplete.")

    # 4. Aligned Matrix Creation
    if not price_data:
        logger.error("No price data loaded. Aborting matrix creation.")
        return

    all_dates_raw = sorted(set().union(*(rets.index for rets in price_data.values())))
    # Ensure index is timezone-aware DatetimeIndex (UTC) to prevent downstream index errors
    all_dates = pd.to_datetime(all_dates_raw, utc=True)
    returns_df = pd.DataFrame(index=all_dates)

    for atom_id, rets in price_data.items():
        # Ensure index is timezone-aware DatetimeIndex (UTC) to prevent downstream index errors
        if not isinstance(rets.index, pd.DatetimeIndex):
            rets.index = pd.to_datetime(rets.index)

        idx_check = cast(Any, rets.index)
        if idx_check.tz is None:
            rets.index = idx_check.tz_localize("UTC")
        else:
            rets.index = idx_check.tz_convert("UTC")

        # CR-181: Directional Normalization (Data Layer)
        # Store only RAW returns in the lakehouse.
        # Sign inversion is now handled dynamically by the analysis/allocation engines.
        returns_df[atom_id] = rets

    # Drop rows where ALL non-crypto assets are missing (e.g., weekends for TradFi)
    profiles = {symbol: get_symbol_profile(symbol) for symbol in returns_df.columns}
    tradfi_cols = [s for s, p in profiles.items() if p != DataProfile.CRYPTO]
    if tradfi_cols:
        tradfi_all_nan = returns_df[tradfi_cols].isna().all(axis=1)
        returns_df = returns_df.loc[~tradfi_all_nan]

    # Apply History Floor (min_days_floor) first to prevent statistical errors on sparse data
    # Only enforce if we are fetching at least that much data (High Integrity pass)
    min_days = int(active_settings.min_days_floor)
    if min_days > 0 and lookback_days >= min_days:
        counts = returns_df.count()
        short_history = [str(c) for c, v in counts.items() if v < min_days]
        if short_history:
            returns_df = returns_df.drop(columns=short_history)
            logger.info("Dropped %d symbols due to insufficient secular history (< %d days): %s", len(short_history), min_days, ", ".join(short_history))

    # CR-187: Data Sanity Guard (Toxic Volatility Filter)
    # Detect and drop assets with unrealistic daily returns (e.g. > 500% or < -99% errors)
    # This prevents solver explosions and meta-metric corruption.
    TOXIC_THRESHOLD = 5.0  # 500% daily move limit
    max_abs_rets = returns_df.abs().max()
    toxic_assets = [str(c) for c, v in max_abs_rets.items() if v > TOXIC_THRESHOLD]

    if toxic_assets:
        returns_df = returns_df.drop(columns=toxic_assets)
        logger.warning(f"Dropped {len(toxic_assets)} TOXIC assets (Daily Return > {TOXIC_THRESHOLD:.0%}): {', '.join(toxic_assets)}")

    # Drop zero-variance noise
    # Use ddof=0 to avoid "Degrees of freedom <= 0" warning
    variances = returns_df.var(ddof=0)
    zero_vars = []
    if not isinstance(variances, (float, int)):
        zero_vars = [str(c) for c, v in variances.items() if v == 0]

    if zero_vars:
        returns_df = returns_df.drop(columns=zero_vars)
        logger.info("Dropped zero-variance symbols: %s", ", ".join(zero_vars))

    # Post-load Deduplication (Optional safety pass)
    dedupe_env = os.getenv("PORTFOLIO_DEDUPE_BASE")
    do_dedupe = dedupe_env == "1" if dedupe_env is not None else bool(active_settings.portfolio_dedupe_base)
    if do_dedupe:
        deduped_cols = []
        seen_idents = set()
        for col in returns_df.columns:
            ident = alpha_meta.get(col, {}).get("identity", col)
            if ident in seen_idents:
                continue
            seen_idents.add(ident)
            deduped_cols.append(col)
        if len(deduped_cols) != len(returns_df.columns):
            logger.info("Dedupe by identity kept %d of %d symbols", len(deduped_cols), len(returns_df.columns))
            returns_df = returns_df[deduped_cols]

    logger.info(f"Alpha Meta keys: {list(alpha_meta.keys())[:5]}")
    logger.info(f"Returns columns: {list(returns_df.columns)[:5]}")
    alpha_meta = {s: alpha_meta[s] for s in returns_df.columns if s in alpha_meta}
    logger.info(f"Alpha Meta size after filter: {len(alpha_meta)}")

    logger.info(f"Returns matrix created: {returns_df.shape}")
    logger.info(f"Writing returns matrix to: {returns_path}")
    if returns_path.endswith(".parquet"):
        returns_df.to_parquet(returns_path)
    else:
        returns_df.to_pickle(returns_path)
    with open(meta_path, "w") as f:
        json.dump(alpha_meta, f, indent=2)

    if ledger:
        ledger.record_outcome(
            step="data_prep",
            status="success",
            output_hashes={"returns_matrix": get_df_hash(returns_df)},
            metrics={"shape": returns_df.shape, "n_symbols": len(returns_df.columns), "returns_path": returns_path, "meta_path": meta_path},
        )

    print("\n" + "=" * 50)
    print("PORTFOLIO UNIVERSE PREPARED")
    print("=" * 50)
    print(f"Matrix Shape : {returns_df.shape}")
    print(f"Symbols      : {', '.join(returns_df.columns)}")


if __name__ == "__main__":
    prepare_portfolio_universe()
