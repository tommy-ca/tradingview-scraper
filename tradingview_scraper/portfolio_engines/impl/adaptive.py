from __future__ import annotations
import dataclasses
import logging
import traceback
from typing import Any, Dict, List, Optional, Tuple, cast

from tradingview_scraper.portfolio_engines.base import BaseRiskEngine, EngineRequest, EngineResponse, ProfileName
from tradingview_scraper.portfolio_engines.impl.custom import CustomClusteredEngine

logger = logging.getLogger(__name__)


class AdaptiveMetaEngine(BaseRiskEngine):
    @property
    def name(self) -> str:
        return "adaptive"

    @classmethod
    def is_available(cls) -> bool:
        return True

    def optimize(self, *, returns, clusters, meta, stats, request):
        from tradingview_scraper.portfolio_engines import build_engine

        mapping = {"EXPANSION": "max_sharpe", "INFLATIONARY_TREND": "barbell", "NORMAL": "max_sharpe", "STAGNATION": "min_variance", "TURBULENT": "hrp", "CRISIS": "hrp"}
        prof = mapping.get(request.market_environment, "benchmark")

        # Warm-up Buffer & Safety Mode
        if len(returns) < 30:
            prof = cast(ProfileName, request.adaptive_fallback_profile)
            logger.info(f"Adaptive Engine: Warm-up active (n={len(returns)} < 30). Falling back to {prof}")

        base = "skfolio" if request.engine == "adaptive" else request.engine
        try:
            engine_obj = build_engine(base)
        except Exception:
            engine_obj = CustomClusteredEngine()

        try:
            resp = engine_obj.optimize(returns=returns, clusters=clusters, meta=meta, stats=stats, request=dataclasses.replace(request, profile=cast(ProfileName, prof)))
            if resp is None or resp.weights.empty:
                raise ValueError("Sub-engine returned empty results")
        except Exception as e:
            fallback_prof = cast(ProfileName, request.adaptive_fallback_profile)
            logger.warning(f"Adaptive Engine sub-solver failed: {e}. Falling back to {fallback_prof}")
            logger.error(traceback.format_exc())
            fallback_engine = CustomClusteredEngine()
            resp = fallback_engine.optimize(returns=returns, clusters=clusters, meta=meta, stats=stats, request=dataclasses.replace(request, profile=cast(ProfileName, fallback_prof)))

        if resp is not None:
            resp.meta.update({"adaptive_profile": prof, "adaptive_base": base})
        return resp
