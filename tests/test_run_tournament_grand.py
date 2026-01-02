from unittest.mock import MagicMock, patch

from scripts.run_4d_tournament import run_4d_tournament


@patch("scripts.run_4d_tournament.BacktestEngine")
@patch("scripts.run_4d_tournament.get_settings")
@patch("builtins.open", new_callable=MagicMock)
def test_run_4d_tournament_rebalance_loop(mock_open, mock_get_settings, mock_bt_class):
    from tradingview_scraper.settings import FeatureFlags

    # Mock settings
    mock_settings = MagicMock()
    mock_settings.features = FeatureFlags()
    mock_settings.prepare_summaries_run_dir.return_value = MagicMock()
    mock_get_settings.return_value = mock_settings

    # Mock BacktestEngine
    captured_configs = []

    def bt_side_effect():
        captured_configs.append(
            {
                "selection": mock_settings.features.selection_mode,
                "rebalance": mock_settings.features.feat_rebalance_mode,
                "tolerance": mock_settings.features.feat_rebalance_tolerance,
                "drift": mock_settings.features.rebalance_drift_limit,
            }
        )
        bt_inst = MagicMock()
        bt_inst.run_tournament.return_value = {"results": {}}
        return bt_inst

    mock_bt_class.side_effect = bt_side_effect

    run_4d_tournament()

    # Selection configs: 2 (v3.1, v3.1_spectral)
    # Rebalance configs: 3 (window, daily, daily_5pct)
    # Total calls: 3 * 2 = 6
    assert len(captured_configs) == 6

    # Check first call: window + v3.1
    assert captured_configs[0]["rebalance"] == "window"
    assert captured_configs[0]["selection"] == "v3.1"

    # Check last call: daily_5pct + v3.1_spectral
    assert captured_configs[5]["rebalance"] == "daily"
    assert captured_configs[5]["tolerance"] is True
    assert captured_configs[5]["drift"] == 0.05
    assert captured_configs[5]["selection"] == "v3.1"
    # Actually v3.1_spectral uses v3.1 mode but with flags
    # Wait, let me check the configs in run_4d_tournament.py

    # selection_configs = [
    #    {"name": "v3.1", "mode": "v3.1", ...},
    #    {"name": "v3.1_spectral", "mode": "v3.1", ...}
    # ]
    # So selection should be v3.1 for both.

    assert captured_configs[5]["selection"] == "v3.1"
