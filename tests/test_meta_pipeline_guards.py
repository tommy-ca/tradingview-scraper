import json

import pandas as pd
import pytest

from scripts.run_meta_pipeline import _assert_meta_report, _assert_meta_returns, _assert_meta_weights


def test_assert_multi_sleeve_meta_pass(tmp_path):
    meta_profile = "meta_test"
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True)

    # Two-sleeve returns
    pd.DataFrame({"a": [0.0, 0.1], "b": [0.0, 0.2]}).to_pickle(data_dir / f"meta_returns_{meta_profile}_hrp.pkl")

    # Two-sleeve weights
    (data_dir / f"meta_optimized_{meta_profile}_hrp.json").write_text(json.dumps({"weights": [{"Symbol": "a", "Weight": 0.5}, {"Symbol": "b", "Weight": 0.5}]}))

    _assert_meta_returns(data_dir, meta_profile)
    _assert_meta_weights(data_dir, meta_profile)


def test_assert_multi_sleeve_meta_fails_on_single_sleeve(tmp_path):
    meta_profile = "meta_test"
    data_dir = tmp_path / "data"
    data_dir.mkdir(parents=True)

    pd.DataFrame({"a": [0.0, 0.1]}).to_pickle(data_dir / f"meta_returns_{meta_profile}_hrp.pkl")
    (data_dir / f"meta_optimized_{meta_profile}_hrp.json").write_text(json.dumps({"weights": [{"Symbol": "a", "Weight": 1.0}]}))

    with pytest.raises(RuntimeError):
        _assert_meta_returns(data_dir, meta_profile)

    with pytest.raises(RuntimeError):
        _assert_meta_weights(data_dir, meta_profile)


def test_assert_meta_report_guard(tmp_path):
    report = tmp_path / "meta_portfolio_report.md"
    report.write_text("# report\n## Sleeve Allocation\n- a", encoding="utf-8")
    _assert_meta_report(report)
