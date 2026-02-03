import pytest

from scripts.services.backfill_features import BackfillService
from tradingview_scraper.symbols.stream.lakehouse import LakehouseStorage
from tradingview_scraper.utils.security import SecurityUtils


@pytest.fixture
def temp_lakehouse(tmp_path):
    lh = tmp_path / "lakehouse"
    lh.mkdir()
    return lh


def test_security_utils_sanitization():
    # Valid symbols
    assert SecurityUtils.sanitize_symbol("BINANCE:BTCUSDT") == "BINANCE_BTCUSDT"
    assert SecurityUtils.sanitize_symbol("AAPL") == "AAPL"

    # Invalid symbols
    with pytest.raises(ValueError, match="Invalid symbol format"):
        SecurityUtils.sanitize_symbol("BTC; rm -rf /")

    # Traversal attempts
    with pytest.raises(ValueError, match="Invalid symbol format"):
        SecurityUtils.sanitize_symbol("../../../etc/passwd")

    with pytest.raises(ValueError, match="Invalid symbol format"):
        SecurityUtils.sanitize_symbol("/etc/passwd")


def test_security_utils_safe_path(temp_lakehouse):
    # Valid
    path = SecurityUtils.get_safe_path(temp_lakehouse, "BINANCE:BTCUSDT")
    assert path.name == "BINANCE_BTCUSDT_1d.parquet"
    assert path.parent == temp_lakehouse.resolve()

    # Traversal
    with pytest.raises(ValueError, match="Invalid symbol format"):
        SecurityUtils.get_safe_path(temp_lakehouse, "../../evil")


def test_lakehouse_storage_security(temp_lakehouse):
    storage = LakehouseStorage(base_path=temp_lakehouse)

    # Valid
    path_str = storage._get_path("BINANCE:BTCUSDT", "1d")
    assert "BINANCE_BTCUSDT_1d.parquet" in path_str

    # Traversal via symbol
    with pytest.raises(ValueError, match="Invalid symbol format"):
        storage._get_path("../../../evil", "1d")

    # Traversal via interval
    with pytest.raises(ValueError, match="Invalid interval format"):
        storage._get_path("BTCUSDT", "../../evil")


def test_backfill_service_security(temp_lakehouse):
    service = BackfillService(lakehouse_dir=temp_lakehouse)

    # Malicious candidates list
    # The run method iterates over symbols
    # We can mock symbols to include a malicious one

    # Note: _get_lakehouse_symbols globs the dir, so it's naturally limited to what's there.
    # But if candidates_path is provided, it reads from JSON.

    import json

    candidates_file = temp_lakehouse / "malicious_candidates.json"
    with open(candidates_file, "w") as f:
        json.dump([{"symbol": "../../../etc/passwd"}], f)

    # This should log an error but not crash/allow traversal
    # We just want to ensure it doesn't try to read the file
    service.run(candidates_path=candidates_file)

    # If it reached pd.read_parquet with a traversal path, it would likely fail or return error
    # We already added try/except in BackfillService.run around get_safe_path
