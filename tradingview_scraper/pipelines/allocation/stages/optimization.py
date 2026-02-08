import logging
from typing import Any, Dict, List, Optional, cast
import pandas as pd
from tradingview_scraper.orchestration.registry import StageRegistry
from tradingview_scraper.pipelines.selection.base import BasePipelineStage
from tradingview_scraper.pipelines.allocation.base import AllocationContext
from tradingview_scraper.portfolio_engines import EngineRequest, ProfileName, build_engine
from tradingview_scraper.settings import get_settings
from tradingview_scraper.utils.synthesis import StrategySynthesizer

logger = logging.getLogger("pipelines.allocation.optimization")


@StageRegistry.register(id="allocation.optimize", name="Optimization", description="Portfolio optimization", category="allocation")
class OptimizationStage(BasePipelineStage):
    """
    Pillar 3: Portfolio Allocation Stage.
    Handles the mathematical optimization of synthesized return streams.
    """

    @property
    def name(self) -> str:
        return "Optimization"

    def __init__(self):
        self.settings = get_settings()
        self.synthesizer = StrategySynthesizer()

    def execute(self, ctx: AllocationContext, engine_name: str, profile: str) -> pd.DataFrame:
        """
        Processes optimization for a single window, engine, and profile.
        Returns flattened weights.
        """
        actual_profile = cast(ProfileName, profile)
        target_engine = engine_name

        if actual_profile in ["market", "benchmark"]:
            target_engine = "market"
        elif actual_profile == "barbell":
            target_engine = "custom"

        opt_ctx = {
            "window_index": ctx.window.step_index,
            "engine": target_engine,
            "profile": profile,
            "regime": ctx.regime_name,
            "actual_profile": actual_profile,
        }

        try:
            solver = build_engine(target_engine)

            if ctx.ledger:
                ctx.ledger.record_intent("backtest_optimize", opt_ctx, input_hashes={})

            req = EngineRequest(
                profile=actual_profile,
                engine=target_engine,
                regime=ctx.regime_name,
                market_environment=ctx.market_env,
                cluster_cap=float(self.settings.cluster_cap),
                kappa_shrinkage_threshold=float(self.settings.features.kappa_shrinkage_threshold),
                default_shrinkage_intensity=float(self.settings.features.default_shrinkage_intensity),
                adaptive_fallback_profile=str(self.settings.features.adaptive_fallback_profile),
                benchmark_returns=ctx.bench_rets,
                market_neutral=(actual_profile == "market_neutral"),
            )

            returns_for_opt = ctx.train_rets if actual_profile == "market" else ctx.train_rets_strat

            # SOLVER CALL (Hardened by decorators in library)
            opt_resp = solver.optimize(returns=returns_for_opt, clusters=ctx.clusters, meta=ctx.window_meta, stats=ctx.stats, request=req)

            if opt_resp.weights.empty:
                return pd.DataFrame()

            if ctx.is_meta:
                return opt_resp.weights

            return self.synthesizer.flatten_weights(opt_resp.weights)

        except Exception as e:
            if ctx.ledger:
                ctx.ledger.record_outcome(step="backtest_optimize", status="error", output_hashes={}, metrics={"error": str(e)}, context=opt_ctx)
            logger.error(f"Optimization failed for {target_engine}/{profile}: {e}")
            return pd.DataFrame()

    def _get_equal_weight_flat(self, returns_for_opt: pd.DataFrame, is_meta: bool) -> pd.DataFrame:
        """Returns equal-weighted portfolio weights."""
        n_strat = len(returns_for_opt.columns)
        if n_strat > 0:
            ew_weights = pd.Series(1.0 / n_strat, index=returns_for_opt.columns)
            dummy_weights = pd.DataFrame({"Symbol": ew_weights.index, "Weight": ew_weights.values})
            return dummy_weights if is_meta else self.synthesizer.flatten_weights(dummy_weights)
        return pd.DataFrame()
