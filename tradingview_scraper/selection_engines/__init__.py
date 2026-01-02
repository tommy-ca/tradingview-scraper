from __future__ import annotations

from typing import Dict, Type

from tradingview_scraper.selection_engines.base import BaseSelectionEngine, SelectionRequest, SelectionResponse
from tradingview_scraper.selection_engines.engines import LegacySelectionEngine, SelectionEngineV2, SelectionEngineV3, SelectionEngineV3_1

SELECTION_ENGINES: Dict[str, Type[BaseSelectionEngine]] = {
    "v2": SelectionEngineV2,
    "v3": SelectionEngineV3,
    "v3.1": SelectionEngineV3_1,
    "legacy": LegacySelectionEngine,
}


def get_selection_engine(name: str) -> BaseSelectionEngine:
    """
    Factory function to retrieve a selection engine by name.
    """
    if name not in SELECTION_ENGINES:
        raise ValueError(f"Unknown selection engine: {name}. Available: {list(SELECTION_ENGINES.keys())}")
    return SELECTION_ENGINES[name]()


__all__ = [
    "BaseSelectionEngine",
    "SelectionRequest",
    "SelectionResponse",
    "get_selection_engine",
    "SELECTION_ENGINES",
]
