import logging
from typing import Any, Dict, List, Optional
import pandas as pd
from tradingview_scraper.pipelines.allocation.base import AllocationContext
from tradingview_scraper.portfolio_engines import build_simulator

logger = logging.getLogger("pipelines.allocation.simulation")


class SimulationStage:
    """
    Pillar 3: Portfolio Simulation Stage.
    Runs simulation and manages state updates.
    """

    def execute(self, ctx: AllocationContext, sim_name: str, engine_name: str, profile: str, weights_df: pd.DataFrame) -> None:
        """Runs simulation and records results."""
        state_key = f"{engine_name}_{sim_name}_{profile}"
        last_state = ctx.current_holdings.get(state_key)

        sim_ctx = {
            "window_index": ctx.window.step_index,
            "engine": engine_name,
            "profile": profile,
            "simulator": sim_name,
        }

        try:
            # 1. Execute Simulator
            simulator = build_simulator(sim_name)
            sim_results = simulator.simulate(weights_df=weights_df, returns=ctx.test_rets, initial_holdings=last_state)

            # 2. Sanitize Metrics
            metrics = self._sanitize_sim_metrics(sim_results)

            # 3. Update State
            self._update_sim_state(ctx, state_key, sim_results, metrics)

            # 4. Record Result
            if ctx.ledger:
                ctx.ledger.record_outcome(step="backtest_simulate", status="success", output_hashes={}, metrics=metrics, context=sim_ctx)

            ctx.results.append({"window": ctx.window.step_index, "engine": engine_name, "profile": profile, "simulator": sim_name, "metrics": metrics})

        except Exception as e:
            if ctx.ledger:
                ctx.ledger.record_outcome(step="backtest_simulate", status="error", output_hashes={}, metrics={"error": str(e)}, context=sim_ctx)
            logger.error(f"Simulation failed for {state_key}: {e}")

    def _sanitize_sim_metrics(self, sim_results: Any) -> dict[str, Any]:
        """Extracts and cleans metrics from simulation results."""
        if isinstance(sim_results, dict):
            return sim_results.get("metrics", sim_results)
        return getattr(sim_results, "metrics", {})

    def _update_sim_state(self, ctx: AllocationContext, state_key: str, sim_results: Any, metrics: dict[str, Any]) -> None:
        """Updates holdings and return series state in context."""
        # Update holdings
        if isinstance(sim_results, dict):
            ctx.current_holdings[state_key] = sim_results.get("final_holdings")
        else:
            ctx.current_holdings[state_key] = getattr(sim_results, "final_holdings", None)

        # Record returns
        daily_rets = metrics.get("daily_returns")
        if isinstance(daily_rets, pd.Series):
            ctx.return_series.setdefault(state_key, []).append(daily_rets.clip(-1.0, 1.0))
