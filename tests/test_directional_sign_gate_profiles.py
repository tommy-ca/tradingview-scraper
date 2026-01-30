import json
from pathlib import Path


def test_short_rating_profiles_have_sign_gate():
    manifest = json.loads(Path("configs/manifest.json").read_text())
    profiles = manifest["profiles"]

    short_profiles = [
        "binance_spot_rating_all_short",
        "binance_spot_rating_ma_short",
    ]

    for name in short_profiles:
        feats = profiles[name].get("features", {})
        assert feats.get("feat_directional_sign_test_gate_atomic") is True, f"{name} must enable feat_directional_sign_test_gate_atomic"
