import logging

import numpy as np
import pandas as pd
from scipy.optimize import minimize
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


class BarbellOptimizer:
    """
    Implements a Taleb-inspired Barbell Strategy.
    Combines a Maximum Diversification Core with high-optionality Aggressors.
    """

    REGIME_SPLITS = {"QUIET": {"core": 0.85, "aggressor": 0.15}, "NORMAL": {"core": 0.90, "aggressor": 0.10}, "CRISIS": {"core": 0.95, "aggressor": 0.05}}

    def _calculate_diversification_ratio(self, weights, returns):
        volatilities = returns.std() * np.sqrt(252)
        # Use shrunk covariance for better stability
        cov_matrix = ShrinkageCovariance().estimate(returns)

        weighted_vol = np.dot(weights, volatilities)
        port_vol = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))

        if port_vol == 0:
            return 0
        return weighted_vol / port_vol

    def optimize(self, returns: pd.DataFrame, antifragility_stats: pd.DataFrame, regime: str = "NORMAL") -> pd.DataFrame:
        """
        Optimizes the barbell portfolio based on the current market regime.
        """
        split = self.REGIME_SPLITS.get(regime, self.REGIME_SPLITS["NORMAL"])
        logger.info(f"Optimizing Barbell for {regime} regime (Core: {split['core']:.0%}, Aggressor: {split['aggressor']:.0%})")

        # 1. Identify Buckets
        # Aggressors: Top 10% or at least 2 assets by Antifragility Score
        n_agg = max(2, int(len(antifragility_stats) * 0.10))
        aggressors = antifragility_stats.sort_values("Antifragility_Score", ascending=False).head(n_agg)["Symbol"].tolist()

        core_candidates = [s for s in returns.columns if s not in aggressors]
        core_returns = returns[core_candidates]

        # 2. Optimize Core (Max Diversification)
        n_core = len(core_candidates)
        init_weights = np.array([1.0 / n_core] * n_core)
        bounds = tuple((0.0, 0.2) for _ in range(n_core))
        constraints = {"type": "eq", "fun": lambda w: np.sum(w) - 1.0}

        res_core = minimize(lambda w: -self._calculate_diversification_ratio(w, core_returns), init_weights, method="SLSQP", bounds=bounds, constraints=constraints)

        # 3. Merge Results
        portfolio = []
        for i, symbol in enumerate(core_candidates):
            portfolio.append({"Symbol": symbol, "Type": "CORE (Safe)", "Weight": res_core.x[i] * split["core"]})

        agg_w = split["aggressor"] / len(aggressors)
        for symbol in aggressors:
            portfolio.append({"Symbol": symbol, "Type": "AGGRESSOR (Antifragile)", "Weight": agg_w})

        return pd.DataFrame(portfolio).sort_values("Weight", ascending=False)
