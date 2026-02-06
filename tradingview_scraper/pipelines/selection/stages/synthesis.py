import logging

import numpy as np
import pandas as pd

from tradingview_scraper.orchestration.registry import StageRegistry
from tradingview_scraper.pipelines.selection.base import BasePipelineStage, SelectionContext
from tradingview_scraper.pipelines.selection.registry import ModelRegistry
from tradingview_scraper.settings import get_settings
from tradingview_scraper.utils.synthesis import StrategyAtom

# Optional MLflow
try:
    from tradingview_scraper.telemetry.mlflow_tracker import MLflowTracker

    HAS_MLFLOW = True
except ImportError:
    HAS_MLFLOW = False

logger = logging.getLogger("pipelines.selection.synthesis")


@StageRegistry.register(id="alpha.synthesis", name="Strategy Synthesis", description="Creates Strategy Atoms from winners", category="alpha")
class SynthesisStage(BasePipelineStage):
    """
    Stage 6: Strategy Synthesis.
    Converts recruited winners into Strategy Atoms and generates the composition map.
    Handles 'Synthetic Long Normalization' by flagging SHORT atoms.
    """

    @property
    def name(self) -> str:
        return "Synthesis"

    def execute(self, context: SelectionContext) -> SelectionContext:
        winners = context.winners
        if not winners:
            logger.warning("SynthesisStage: No winners to synthesize.")
            return context

        logger.info(f"Synthesizing {len(winners)} Strategy Atoms...")

        atoms = []
        comp_map = {}

        for w in winners:
            sym = str(w["symbol"])
            logic = str(w.get("logic", "momentum"))  # Default logic if not specified (v3 assumes momentum/trend)
            direction = str(w.get("direction", "LONG"))

            # Create Atom
            atom = StrategyAtom(asset=sym, logic=logic, direction=direction)
            atoms.append(atom)

            # Generate Composition Map (Atom ID -> {Asset: Weight})
            # Weight is 1.0 for LONG, -1.0 for SHORT (Synthetic Long Normalization)
            weight = 1.0 if direction == "LONG" else -1.0
            comp_map[atom.id] = {sym: weight}

        context.strategy_atoms = atoms
        context.composition_map = comp_map

        context.log_event(self.name, "SynthesisComplete", {"n_atoms": len(atoms), "n_shorts": len([a for a in atoms if a.direction == "SHORT"])})

        # New Logic: Calculate In-Sample Performance and Register
        self._check_and_register_candidate(context, atoms)

        return context

    def _check_and_register_candidate(self, context: SelectionContext, atoms: list[StrategyAtom]):
        """Calculates simple in-sample metrics and registers if promising."""
        if context.returns_df.empty:
            return

        try:
            settings = get_settings()
            # Simple Equal-Weight Synthetic Portfolio
            series_list = []
            for atom in atoms:
                if atom.asset in context.returns_df.columns:
                    ret_series = context.returns_df[atom.asset].copy()
                    if atom.direction == "SHORT":
                        ret_series = -1.0 * ret_series
                    series_list.append(ret_series)

            if not series_list:
                return

            # Combine
            portfolio_returns = pd.concat(series_list, axis=1).mean(axis=1)

            # Drop NaN
            portfolio_returns = portfolio_returns.dropna()

            if len(portfolio_returns) < 20:  # Minimum history check
                return

            # Annualized Sharpe
            mean_ret = portfolio_returns.mean()
            std_ret = portfolio_returns.std()

            if std_ret == 0:
                sharpe = 0.0
            else:
                sharpe = (mean_ret / std_ret) * np.sqrt(252)

            # Calculate Max Drawdown
            cum_ret = (1 + portfolio_returns).cumprod()
            peak = cum_ret.cummax()
            drawdown = (cum_ret - peak) / peak
            max_dd = float(drawdown.min())

            # Phase 1: MLflow Tracking
            if HAS_MLFLOW:
                try:
                    tracker = MLflowTracker(experiment_name=context.run_id)
                    tracker.log_metrics({"sharpe": float(sharpe), "max_dd": max_dd, "n_atoms": len(atoms), "mean_daily_ret": float(mean_ret), "annual_vol": float(std_ret * np.sqrt(252))})
                except Exception as e:
                    logger.warning(f"MLflow logging failed in SynthesisStage: {e}")

            threshold = 1.5  # Per user request example

            if sharpe > threshold:
                logger.info(f"High-Potential Candidate Detected (In-Sample Sharpe: {sharpe:.2f}). Registering...")

                # Derive Run Dir
                run_dir = settings.summaries_dir / "runs" / context.run_id

                registry = ModelRegistry(run_dir)
                registry.register_model(
                    run_id=context.run_id,
                    metrics={
                        "sharpe": float(sharpe),
                        "max_dd": max_dd,
                        "mean_return": float(mean_ret),
                        "volatility": float(std_ret * np.sqrt(252)),
                        "n_atoms": len(atoms),
                    },
                    tags=["candidate", "high_sharpe", "in_sample"],
                )

                context.log_event(self.name, "ModelRegistered", {"sharpe": float(sharpe)})

        except Exception as e:
            logger.warning(f"Failed to register candidate model: {e}")
