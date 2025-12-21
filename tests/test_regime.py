import unittest

import pandas as pd

from tradingview_scraper.regime import MarketRegimeDetector


class TestMarketRegimeDetector(unittest.TestCase):
    def test_detect_regime_quiet(self):
        # Setup low-vol returns
        returns = pd.DataFrame({"A": [0.001, -0.001] * 15, "B": [0.001, -0.001] * 15})

        detector = MarketRegimeDetector()
        regime = detector.detect_regime(returns)
        # Ratio should be ~1.0 (NORMAL) unless we make it really quiet at the end
        # Let's make it QUIET at the end
        returns.iloc[-5:] = 0.00001
        regime = detector.detect_regime(returns)
        self.assertEqual(regime, "QUIET")

    def test_detect_regime_crisis(self):
        # Setup high-vol spike at the end
        data = [0.001, -0.001] * 15
        returns = pd.DataFrame({"A": data, "B": data})
        # Last 5 are extremely volatile
        spike = [0.1, -0.1, 0.1, -0.1, 0.1]
        returns.iloc[-5:, 0] = spike
        returns.iloc[-5:, 1] = spike

        detector = MarketRegimeDetector()
        regime = detector.detect_regime(returns)
        self.assertEqual(regime, "CRISIS")


if __name__ == "__main__":
    unittest.main()
