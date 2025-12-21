import unittest

import numpy as np
import pandas as pd

from tradingview_scraper.risk import ShrinkageCovariance


class TestShrinkageCovariance(unittest.TestCase):
    def test_ledoit_wolf_estimate(self):
        # Create a small, potentially singular dataset
        # 5 assets, but only 10 days of data
        data = np.random.normal(0, 0.01, (10, 5))
        returns = pd.DataFrame(data)

        estimator = ShrinkageCovariance()
        cov_shrunk = estimator.estimate(returns)

        self.assertEqual(cov_shrunk.shape, (5, 5))
        # Naive covariance might be ill-conditioned, shrunk should be better
        # Just verify it's a valid positive semi-definite matrix
        self.assertTrue(np.all(np.linalg.eigvals(cov_shrunk) > 0))


if __name__ == "__main__":
    unittest.main()
