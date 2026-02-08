import json
from pathlib import Path

import pandas as pd

from scripts.generate_meta_report import generate_meta_markdown_report


def _write_meta_files(base: Path, meta_profile: str, risk_profile: str):
    base.mkdir(parents=True, exist_ok=True)
    # meta returns with two sleeves
    pd.DataFrame({"a": [0.0, 0.1], "b": [0.0, 0.2]}).to_pickle(base / f"meta_returns_{meta_profile}_{risk_profile}.pkl")

    meta_opt = {
        "metadata": {"run_id": f"{meta_profile}_run"},
        "weights": [
            {"Symbol": "a", "Weight": 0.5},
            {"Symbol": "b", "Weight": 0.5},
        ],
    }
    (base / f"meta_optimized_{meta_profile}_{risk_profile}.json").write_text(json.dumps(meta_opt))

    flat = {
        "weights": [
            {"Symbol": "PHYSICAL_A", "Weight": 0.5, "Net_Weight": 0.5, "Contributors": ["a"], "Market": "UNKNOWN"},
            {"Symbol": "PHYSICAL_B", "Weight": 0.5, "Net_Weight": 0.5, "Contributors": ["b"], "Market": "UNKNOWN"},
        ]
    }
    (base / f"portfolio_optimized_meta_{meta_profile}_{risk_profile}.json").write_text(json.dumps(flat))

    cluster = {"weights": [{"Symbol": "a", "Weight": 0.5}, {"Symbol": "b", "Weight": 0.5}]}
    (base / f"meta_cluster_tree_{meta_profile}_{risk_profile}.json").write_text(json.dumps(cluster))


def test_meta_report_pass(tmp_path):
    meta_dir = tmp_path / "meta"
    meta_profile = "meta_test"
    risk_profile = "hrp"
    _write_meta_files(meta_dir, meta_profile, risk_profile)

    # sign test file present and passing
    (meta_dir / "directional_sign_test.json").write_text(json.dumps({"errors": 0, "warnings": 0, "findings": []}))

    out = tmp_path / "report.md"
    generate_meta_markdown_report(meta_dir, str(out), [risk_profile], meta_profile)

    assert out.exists()
    content = out.read_text()
    assert "Sleeve Allocation" in content


def test_meta_report_missing_sign_test_fails(tmp_path):
    meta_dir = tmp_path / "meta"
    meta_profile = "meta_test"
    risk_profile = "hrp"
    _write_meta_files(meta_dir, meta_profile, risk_profile)

    out = tmp_path / "report.md"
    try:
        generate_meta_markdown_report(meta_dir, str(out), [risk_profile], meta_profile)
    except RuntimeError:
        return
    raise AssertionError("Expected RuntimeError when sign test file is missing")
