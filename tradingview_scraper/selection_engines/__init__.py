from __future__ import annotations

from typing import Dict, Type

from tradingview_scraper.selection_engines.base import BaseSelectionEngine, SelectionRequest, SelectionResponse
from tradingview_scraper.selection_engines.engines import (
    SelectionEngineV2,
    SelectionEngineV2_0,
    SelectionEngineV2_1,
    SelectionEngineV3,
    SelectionEngineV3_1,
    SelectionEngineV3_2,
    SelectionEngineV3_4,
)

SELECTION_ENGINES: Dict[str, Type[BaseSelectionEngine]] = {
    "v2.0": SelectionEngineV2_0,
    "v2": SelectionEngineV2,
    "v2.1": SelectionEngineV2_1,
    "v3": SelectionEngineV3,
    "v3.1": SelectionEngineV3_1,
    "v3.2": SelectionEngineV3_2,
    "v3.4": SelectionEngineV3_4,
    "legacy": SelectionEngineV2_0,  # Alias for backward compatibility
}


def build_selection_engine(mode: str) -> BaseSelectionEngine:
    if mode not in SELECTION_ENGINES:
        raise ValueError(f"Unknown selection mode: {mode}")
    return SELECTION_ENGINES[mode]()


def get_selection_engine(mode: str) -> BaseSelectionEngine:
    return build_selection_engine(mode)
