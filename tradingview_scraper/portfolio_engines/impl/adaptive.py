from __future__ import annotations
import dataclasses
import logging
import traceback
from typing import Any, Dict, List, Optional, Tuple, cast

from tradingview_scraper.portfolio_engines.base import BaseRiskEngine, EngineRequest, EngineResponse, ProfileName
from tradingview_scraper.portfolio_engines.impl.custom import CustomClusteredEngine

logger = logging.getLogger(__name__)


class AdaptiveMetaEngine(BaseRiskEngine):
    """
    Regime-Aware Meta-Engine.
    Dynamically maps market environments to optimal risk profiles.
    """

    @property
    def name(self) -> str:
        return "adaptive"

    @classmethod
    def is_available(cls) -> bool:
        return True

    def optimize(self, *, returns, clusters, meta, stats, request):
        from tradingview_scraper.portfolio_engines import build_engine

        # 1. Regime Mapping
        mapping = {"EXPANSION": "max_sharpe", "INFLATIONARY_TREND": "barbell", "NORMAL": "max_sharpe", "STAGNATION": "min_variance", "TURBULENT": "hrp", "CRISIS": "hrp"}
        target_prof = mapping.get(request.market_environment, "equal_weight")

        # 2. Warm-up Buffer (CRP-221)
        if len(returns) < 30:
            target_prof = cast(ProfileName, request.adaptive_fallback_profile)
            logger.info(f"Adaptive Engine: Warm-up active (n={len(returns)} < 30). Falling back to {target_prof}")

        # 3. Recruit Sub-Solver
        # We use skfolio as the default high-fidelity backend for adaptive
        sub_engine_name = "skfolio" if request.engine in ["adaptive", "custom"] else request.engine
        try:
            sub_solver = build_engine(sub_engine_name)
        except Exception:
            sub_solver = CustomClusteredEngine()

        # 4. Execute Optimization with Regime-Mapped Profile
        try:
            resp = sub_solver.optimize(returns=returns, clusters=clusters, meta=meta, stats=stats, request=dataclasses.replace(request, profile=cast(ProfileName, target_prof)))
            if resp is None or resp.weights.empty:
                raise ValueError(f"Sub-solver {sub_engine_name} returned empty weights for {target_prof}")
        except Exception as e:
            # Recursive SSP Fallback to ERC
            fallback_prof = cast(ProfileName, request.adaptive_fallback_profile)
            logger.warning(f"Adaptive Engine sub-solver ({sub_engine_name}) failed: {e}. Falling back to {fallback_prof}")
            fallback_engine = CustomClusteredEngine()
            resp = fallback_engine.optimize(returns=returns, clusters=clusters, meta=meta, stats=stats, request=dataclasses.replace(request, profile=cast(ProfileName, fallback_prof)))

        if resp is not None:
            resp.meta.update({"adaptive_target": target_prof, "adaptive_backend": sub_engine_name, "is_adaptive": True})
        return resp
