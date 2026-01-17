from abc import ABC, abstractmethod
from typing import List

from tradingview_scraper.pipelines.selection.base import SelectionContext


class BaseRanker(ABC):
    """
    Abstract interface for candidate ranking logic.
    Decouples sorting/scoring from the Policy Stage.
    """

    @abstractmethod
    def rank(self, candidates: List[str], context: SelectionContext, ascending: bool = False) -> List[str]:
        """
        Sorts the candidate list based on the ranker's logic.

        Args:
            candidates: List of symbol IDs (atoms) to sort.
            context: Full selection context (features, inference_outputs, metadata).
            ascending: Sort direction (True=Low->High, False=High->Low).

        Returns:
            A new list of symbol IDs sorted by rank.
        """
        pass
