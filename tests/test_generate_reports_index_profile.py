import json
from types import SimpleNamespace

from scripts.generate_reports import ReportGenerator


def test_resolved_profile_name_uses_resolved_manifest(tmp_path):
    inst = object.__new__(ReportGenerator)
    inst.config_dir = tmp_path
    inst.settings = SimpleNamespace(profile="fallback")
    (tmp_path / "resolved_manifest.json").write_text(json.dumps({"profile": "resolved_prof"}))

    assert inst._resolved_profile_name() == "resolved_prof"


def test_resolved_profile_name_fallback_without_file(tmp_path):
    inst = object.__new__(ReportGenerator)
    inst.config_dir = tmp_path
    inst.settings = SimpleNamespace(profile="fallback")

    assert inst._resolved_profile_name() == "fallback"
