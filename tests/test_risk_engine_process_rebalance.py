from types import SimpleNamespace

import pandas as pd

from tradingview_scraper.risk.engine import RiskManagementEngine


def test_process_rebalance_veto_non_string_index_overwrites_not_inserts():
    # Regression test: if index keys are non-strings, we must not add new string keys.
    settings = SimpleNamespace(
        initial_capital=1000.0,
        max_daily_loss_pct=0.05,
        max_total_loss_pct=0.10,
        features=None,
    )
    engine = RiskManagementEngine(settings)

    target_weights = pd.Series([0.6, 0.4], index=pd.Index([1, 2], dtype="int64"))
    engine.context.veto_registry.add_veto("1", reason="test", value=0.0)

    final_weights = engine.process_rebalance(target_weights)

    assert final_weights.index.equals(target_weights.index)
    assert len(final_weights) == len(target_weights)
    assert "1" not in final_weights.index
    assert final_weights.loc[1] == 0.0
