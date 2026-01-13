import json
import logging
import os

import pandas as pd

from tradingview_scraper.pipelines.selection.base import BasePipelineStage, SelectionContext

logger = logging.getLogger("pipelines.selection.ingestion")


class IngestionStage(BasePipelineStage):
    """
    Stage 1: Multi-Sleeve Ingestion.
    Loads raw candidates and return data from the Lakehouse.
    """

    @property
    def name(self) -> str:
        return "Ingestion"

    def __init__(self, candidates_path: str = "data/lakehouse/portfolio_candidates.json", returns_path: str = "data/lakehouse/portfolio_returns.csv"):
        self.candidates_path = candidates_path
        self.returns_path = returns_path

    def execute(self, context: SelectionContext) -> SelectionContext:
        logger.info(f"Executing Ingestion Stage from {self.candidates_path}")

        # 1. Load Candidates
        if not os.path.exists(self.candidates_path):
            raise FileNotFoundError(f"Candidates manifest not found: {self.candidates_path}")

        with open(self.candidates_path, "r") as f:
            context.raw_pool = json.load(f)

        # 2. Load Returns
        if not os.path.exists(self.returns_path):
            logger.warning(f"Returns matrix not found at {self.returns_path}. Initializing empty.")
            context.returns_df = pd.DataFrame()
        else:
            ext = os.path.splitext(self.returns_path)[1].lower()
            if ext == ".parquet":
                context.returns_df = pd.read_parquet(self.returns_path)
            elif ext in [".pkl", ".pickle"]:
                context.returns_df = pd.read_pickle(self.returns_path)
            else:
                context.returns_df = pd.read_csv(self.returns_path, index_col=0, parse_dates=True)

        context.log_event(self.name, "DataLoaded", {"n_candidates": len(context.raw_pool), "returns_shape": context.returns_df.shape})

        return context
