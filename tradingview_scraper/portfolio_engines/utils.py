import logging
from typing import Any, Callable, Optional

import pandas as pd

from tradingview_scraper.portfolio_engines.backtest_simulators import build_simulator
from tradingview_scraper.portfolio_engines.base import EngineRequest

logger = logging.getLogger(__name__)


def harden_solve(
    solver: Any,
    returns: pd.DataFrame,
    clusters: dict[str, list[str]],
    window_meta: dict[str, Any],
    stats: pd.DataFrame,
    request: EngineRequest,
    test_rets: pd.DataFrame,
    sim_name: str,
    current_holdings: dict[str, Any],
    synthesizer: Any,
    is_meta: bool,
    apply_constraints_fn: Callable[[pd.DataFrame], None],
    get_ew_fn: Callable[[], pd.DataFrame],
    ledger: Optional[Any] = None,
) -> pd.DataFrame:
    """
    Standardized solver execution with numerical hardening (Ridge retries) and stability checks.
    """
    default_shrinkage = request.default_shrinkage_intensity
    if request.profile == "max_sharpe":
        default_shrinkage = max(default_shrinkage, 0.15)

    current_ridge = default_shrinkage
    max_ridge_retries = 3
    ridge_attempt = 0
    final_flat_weights = pd.DataFrame()

    while ridge_attempt < max_ridge_retries:
        ridge_attempt += 1

        # Create modified request for retry
        from dataclasses import replace

        active_req = replace(request, default_shrinkage_intensity=current_ridge)

        if ledger and ridge_attempt > 1:
            ledger.record_intent("backtest_optimize_retry", {"attempt": ridge_attempt, "ridge": current_ridge}, input_hashes={})

        try:
            opt_resp = solver.optimize(returns=returns, clusters=clusters, meta=window_meta, stats=stats, request=active_req)

            if is_meta:
                flat_weights = opt_resp.weights
            else:
                flat_weights = synthesizer.flatten_weights(opt_resp.weights)

            if not flat_weights.empty:
                apply_constraints_fn(flat_weights)

            if flat_weights.empty:
                break

            # Stability Verification (Window Veto)
            simulator = build_simulator(sim_name)
            state_key = f"{request.engine}_{sim_name}_{request.profile}"
            last_state = current_holdings.get(state_key)
            sim_results = simulator.simulate(weights_df=flat_weights, returns=test_rets, initial_holdings=last_state)

            metrics = sim_results.get("metrics", sim_results) if isinstance(sim_results, dict) else getattr(sim_results, "metrics", {})
            sharpe = float(metrics.get("sharpe", 0.0))

            if sharpe > 10.0 and ridge_attempt < max_ridge_retries and request.profile not in ["market", "benchmark"]:
                current_ridge = 0.50 if ridge_attempt == 1 else 0.95
                logger.warning(f"  [ADAPTIVE RIDGE] Solver anomalous (Sharpe={sharpe:.2f}). Retrying with Ridge={current_ridge:.2f}")
                continue

            if sharpe > 10.0 and request.profile not in ["market", "benchmark"]:
                logger.warning("  [WINDOW VETO] Unstable result. Forcing Equal Weight.")
                flat_weights = get_ew_fn()

            final_flat_weights = flat_weights
            break

        except Exception as e:
            logger.warning(f"  [SOLVER FAIL] attempt {ridge_attempt}: {e}")
            if ridge_attempt >= max_ridge_retries:
                return get_ew_fn()
            current_ridge = 0.50 if ridge_attempt == 1 else 0.95

    return final_flat_weights
