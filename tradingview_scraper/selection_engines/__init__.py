from __future__ import annotations

from typing import Dict, Type

from tradingview_scraper.selection_engines.base import BaseSelectionEngine
from tradingview_scraper.selection_engines.engines import (
    LegacySelectionEngine,
    SelectionEngineV2,
    SelectionEngineV3,
    SelectionEngineV3_1,
    SelectionEngineV3_2,
)

SELECTION_ENGINES: Dict[str, Type[BaseSelectionEngine]] = {
    "v2": SelectionEngineV2,
    "v3": SelectionEngineV3,
    "v3.1": SelectionEngineV3_1,
    "v3.2": SelectionEngineV3_2,
    "legacy": LegacySelectionEngine,
}


def build_selection_engine(mode: str) -> BaseSelectionEngine:
    if mode not in SELECTION_ENGINES:
        raise ValueError(f"Unknown selection mode: {mode}")
    return SELECTION_ENGINES[mode]()
