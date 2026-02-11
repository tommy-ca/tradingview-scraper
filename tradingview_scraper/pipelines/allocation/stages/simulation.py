import logging
from typing import Any, Dict, List, Optional
import pandas as pd
from tradingview_scraper.orchestration.registry import StageRegistry
from tradingview_scraper.pipelines.selection.base import BasePipelineStage
from tradingview_scraper.pipelines.allocation.base import AllocationContext
from tradingview_scraper.portfolio_engines import build_simulator

logger = logging.getLogger("pipelines.allocation.simulation")


@StageRegistry.register(id="allocation.simulate", name="Simulation", description="Portfolio simulation", category="allocation")
class SimulationStage(BasePipelineStage):
    """
    Pillar 3: Portfolio Simulation Stage.
    Runs simulation and manages state updates.
    """

    @property
    def name(self) -> str:
        return "Simulation"

    def execute(self, ctx: AllocationContext, sim_name: str, engine_name: str, profile: str, weights_df: pd.DataFrame) -> AllocationContext:
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
            # 0. Physical Normalization (CR-832)
            # Map Strategy/Atom weights -> Physical Asset weights
            # If is_meta, this is effectively an identity pass (Sleeve -> Sleeve)
            final_weights = self._flatten_weights(weights_df, ctx.composition_map)

            # 1. Execute Simulator
            settings = get_settings()
            # Extract exit rules from settings (L3 tactical risk)
            exit_rules = settings.exit_rules or {}

            simulator = build_simulator(sim_name)
            sim_results = simulator.simulate(
                weights_df=final_weights,
                returns=ctx.test_rets,
                initial_holdings=last_state,
                # Pass exit rules to the simulator for discrete monitoring
                **exit_rules,
            )

            # 2. Sanitize Metrics
            metrics = self._sanitize_sim_metrics(sim_results)

            # 3. Update State
            self._update_sim_state(ctx, state_key, sim_results, metrics)

            # 4. Record Result
            if ctx.ledger:
                ctx.ledger.record_outcome(step="backtest_simulate", status="success", output_hashes={}, metrics=metrics, context=sim_ctx)

            ctx.results.append({"window": ctx.window.step_index, "engine": engine_name, "profile": profile, "simulator": sim_name, "metrics": metrics})

            return ctx

        except Exception as e:
            if ctx.ledger:
                ctx.ledger.record_outcome(step="backtest_simulate", status="error", output_hashes={}, metrics={"error": str(e)}, context=sim_ctx)
            logger.error(f"Simulation failed for {state_key}: {e}")
            return ctx

    def _flatten_weights(self, strategy_weights: pd.DataFrame, composition_map: Dict[str, Dict[str, float]]) -> pd.DataFrame:
        """
        Maps strategy weights back to physical assets.
        Expects a DataFrame with 'Symbol' and 'Weight' columns.
        """
        asset_weights: Dict[str, float] = {}

        for _, row in strategy_weights.iterrows():
            strat_name = str(row["Symbol"])
            weight = float(row["Weight"])

            if strat_name in composition_map:
                comp = composition_map[strat_name]
                for asset, factor in comp.items():
                    asset_weights[asset] = asset_weights.get(asset, 0.0) + (weight * factor)
            else:
                # Identity fallback (e.g. Meta sleeves or raw assets)
                asset_weights[strat_name] = asset_weights.get(strat_name, 0.0) + weight

        flat_rows = [{"Symbol": k, "Weight": abs(v), "Net_Weight": v} for k, v in asset_weights.items()]
        if not flat_rows:
            return pd.DataFrame(columns=pd.Index(["Symbol", "Weight", "Net_Weight"]))

        return pd.DataFrame(flat_rows).sort_values("Weight", ascending=False)

    def _sanitize_sim_metrics(self, sim_results: Any) -> dict[str, Any]:
        """Extracts and cleans metrics from simulation results."""
        import numpy as np

        metrics = {}
        if isinstance(sim_results, dict):
            metrics = sim_results.get("metrics", sim_results)
        else:
            metrics = getattr(sim_results, "metrics", {})

        # Deep clean types for JSON serialization
        def _clean(obj: Any) -> Any:
            if isinstance(obj, (pd.Series, np.ndarray)):
                return obj.tolist()
            if isinstance(obj, (np.integer, int)):
                return int(obj)
            if isinstance(obj, (np.floating, float)):
                return float(obj)
            if isinstance(obj, dict):
                return {k: _clean(v) for k, v in obj.items()}
            if isinstance(obj, list):
                return [_clean(x) for x in obj]
            return obj

        return _clean(metrics)

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
