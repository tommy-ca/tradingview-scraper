import logging

import pandas as pd
from sklearn.covariance import ledoit_wolf

logger = logging.getLogger(__name__)


class ShrinkageCovariance:
    """
    Provides robust covariance matrix estimation using Ledoit-Wolf shrinkage.
    Useful for small sample sizes or highly correlated assets (common in crypto).
    """

    def estimate(self, returns: pd.DataFrame) -> pd.DataFrame:
        """
        Estimates the shrunk covariance matrix.

        Args:
            returns: DataFrame of daily returns.

        Returns:
            DataFrame: Shrunk covariance matrix.
        """
        if returns.empty:
            return pd.DataFrame()

        # Ledoit-Wolf Shrinkage
        # returns.values expected shape: (n_samples, n_features)
        shrunk_cov, shrinkage = ledoit_wolf(returns.values)

        logger.info(f"Covariance estimated with Ledoit-Wolf (Shrinkage: {shrinkage:.4f})")

        return pd.DataFrame(shrunk_cov, index=returns.columns, columns=returns.columns)
