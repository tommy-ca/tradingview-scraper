from unittest.mock import MagicMock, patch

from scripts.run_4d_tournament import run_4d_tournament


@patch("scripts.run_4d_tournament.BacktestEngine")
@patch("scripts.run_4d_tournament.get_settings")
@patch("builtins.open", new_callable=MagicMock)
def test_run_4d_tournament_config_loop(mock_open, mock_get_settings, mock_bt_class):
    from tradingview_scraper.settings import FeatureFlags

    # Mock settings
    mock_settings = MagicMock()
    mock_settings.features = FeatureFlags()
    mock_settings.prepare_summaries_run_dir.return_value = MagicMock()
    mock_get_settings.return_value = mock_settings

    # Mock BacktestEngine
    captured_settings = []

    def bt_side_effect():
        from copy import deepcopy

        captured_settings.append(deepcopy(mock_settings.features))
        bt_inst = MagicMock()
        bt_inst.run_tournament.return_value = {"results": {}}
        return bt_inst

    mock_bt_class.side_effect = bt_side_effect

    run_4d_tournament()

    # Check that BacktestEngine was instantiated 5 times
    assert len(captured_settings) == 5

    # Check that settings were updated correctly in each call
    assert captured_settings[0].selection_mode == "v2"
    assert captured_settings[1].selection_mode == "v3"
    assert captured_settings[2].selection_mode == "v3"
    assert captured_settings[2].feat_predictability_vetoes is True
    assert captured_settings[3].selection_mode == "v3.1"
    assert captured_settings[4].selection_mode == "v3.1"
    assert captured_settings[4].feat_predictability_vetoes is True

    # Verify restoration
    assert mock_settings.features.selection_mode == "v3"  # default
