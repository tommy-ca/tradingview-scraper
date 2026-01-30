import json

import pandas as pd

from scripts import validate_meta_run as vmr


def test_meta_validation_fails_on_single_sleeve(tmp_path, monkeypatch):
    run_dir = tmp_path / "meta_single"
    data_dir = run_dir / "data"
    reports_dir = run_dir / "reports" / "validation"
    data_dir.mkdir(parents=True)
    reports_dir.mkdir(parents=True)

    # Meta returns with a single sleeve
    meta_profile = "meta_test"
    risk_profile = "hrp"
    meta_returns_path = data_dir / f"meta_returns_{meta_profile}_{risk_profile}.pkl"
    pd.DataFrame({"long_all": [0.01, 0.02]}).to_pickle(meta_returns_path)

    # Optimized weights with a single sleeve
    (data_dir / f"meta_optimized_{meta_profile}_{risk_profile}.json").write_text(json.dumps({"weights": [{"Symbol": "long_all", "Weight": 1.0}]}))

    # Flattened weights (single)
    (data_dir / f"portfolio_optimized_meta_{meta_profile}_{risk_profile}.json").write_text(json.dumps({"weights": [{"Symbol": "PHYSICAL_LONG_ALL", "Weight": 1.0, "Net_Weight": 1.0}]}))

    # Cluster tree stub
    (data_dir / f"meta_cluster_tree_{meta_profile}_{risk_profile}.json").write_text(json.dumps({"weights": [{"Symbol": "long_all", "Weight": 1.0}]}))

    # Monkeypatch run resolution to the temp run dir
    monkeypatch.setattr(vmr, "_resolve_run_dir", lambda run_id: run_dir)
    monkeypatch.setattr(vmr, "_summaries_run_dir", lambda: tmp_path)

    # Expect failure due to single-sleeve meta
    exit_code = vmr.validate_meta_run(
        run_id="meta_single",
        meta_profile=meta_profile,
        risk_profiles=[risk_profile],
    )

    assert exit_code == 1
