from unittest.mock import MagicMock, patch

import numpy as np
import pandas as pd
import pytest

from tradingview_scraper.selection_engines.base import SelectionRequest
from tradingview_scraper.selection_engines.engines import SelectionEngineV3_1, SelectionEngineV3_2
from tradingview_scraper.settings import FeatureFlags


def test_v3_2_logmps_parity_with_v3_1():
    """Verify that v3.2 with default weights matches v3.1 logic results."""
    np.random.seed(42)
    n_days = 100
    n_syms = 10
    returns = pd.DataFrame(np.random.randn(n_days, n_syms) * 0.01 + 0.001, columns=[f"S{i}" for i in range(n_syms)])

    raw_candidates = [{"symbol": f"S{i}", "direction": "LONG", "Value.Traded": 1e9, "tick_size": 0.01, "lot_size": 1, "price_precision": 2} for i in range(n_syms)]

    request = SelectionRequest(top_n=3, threshold=0.5, max_clusters=5, min_momentum_score=-1.0)

    engine_v31 = SelectionEngineV3_1()
    engine_v32 = SelectionEngineV3_2()

    # Run v3.1
    res_v31 = engine_v31.select(returns, raw_candidates, stats_df=None, request=request)

    # Run v3.2 with flag ON and default weights
    with patch("tradingview_scraper.selection_engines.engines.get_settings") as mock_get:
        # We need to preserve other flags if they affect selection
        # Default FeatureFlags has most things off.
        mock_get.return_value.features = FeatureFlags(feat_selection_logmps=True)
        res_v32 = engine_v32.select(returns, raw_candidates, stats_df=None, request=request)

    assert [w["symbol"] for w in res_v32.winners] == [w["symbol"] for w in res_v31.winners]

    # Check alpha scores parity (should be very close)
    scores_v31 = res_v31.metrics["alpha_scores"]
    scores_v32 = res_v32.metrics["alpha_scores"]

    for sym in scores_v31:
        assert pytest.approx(scores_v31[sym], rel=1e-5) == scores_v32[sym]


def test_v3_2_flag_off_fallback():
    """Verify that v3.2 falls back to v3.1 if flag is off."""
    engine_v32 = SelectionEngineV3_2()

    with patch("tradingview_scraper.selection_engines.engines.get_settings") as mock_get:
        mock_get.return_value.features = FeatureFlags(feat_selection_logmps=False)
        # Using MagicMock for dependencies to just check call
        with patch("tradingview_scraper.selection_engines.engines.SelectionEngineV3_1") as MockV31:
            mock_v31_inst = MockV31.return_value
            engine_v32.select(pd.DataFrame(), [], None, MagicMock())
            assert mock_v31_inst.select.called
