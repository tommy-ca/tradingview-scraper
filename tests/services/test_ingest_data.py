import json
import os
import sys
import time
from unittest.mock import ANY, patch

import pandas as pd
import pytest

sys.path.append(os.getcwd())


class MockPersistentLoader:
    def __init__(self):
        self.sync_called = []

    def sync(self, symbol, interval, depth, total_timeout):
        self.sync_called.append(symbol)

    def load(self, symbol, start, end, interval):
        # Return dummy dataframe
        return pd.DataFrame({"timestamp": [1, 2, 3], "close": [100.0, 101.0, 102.0]})


@pytest.fixture
def mock_loader():
    return MockPersistentLoader()


@pytest.fixture
def temp_lakehouse(tmp_path):
    lake_dir = tmp_path / "data" / "lakehouse"
    lake_dir.mkdir(parents=True)
    return lake_dir


def test_idempotency_fresh_skip(temp_lakehouse):
    """Test that fresh files are skipped."""
    symbol = "BINANCE:BTCUSDT"
    safe_sym = "BINANCE_BTCUSDT"

    # Create a fresh file
    p_path = temp_lakehouse / f"{safe_sym}_1d.parquet"
    pd.DataFrame({"close": [1]}).to_parquet(p_path)

    # Mock time to make it look fresh (< 12 hours)
    current_time = time.time()
    os.utime(p_path, (current_time, current_time))

    with patch("scripts.services.ingest_data.PersistentDataLoader") as MockLoaderClass:
        loader_instance = MockLoaderClass.return_value

        from scripts.services.ingest_data import IngestionService

        service = IngestionService(lakehouse_dir=temp_lakehouse, freshness_hours=12)
        service.ingest([{"symbol": symbol}])

        # Verify sync was NOT called
        loader_instance.sync.assert_not_called()


def test_idempotency_stale_fetch(temp_lakehouse):
    """Test that stale files trigger a fetch."""
    symbol = "BINANCE:ETHUSDT"
    safe_sym = "BINANCE_ETHUSDT"

    # Create a stale file (> 12 hours old)
    p_path = temp_lakehouse / f"{safe_sym}_1d.parquet"
    pd.DataFrame({"close": [1]}).to_parquet(p_path)

    stale_time = time.time() - (13 * 3600)
    os.utime(p_path, (stale_time, stale_time))

    with patch("scripts.services.ingest_data.PersistentDataLoader") as MockLoaderClass:
        loader_instance = MockLoaderClass.return_value

        from scripts.services.ingest_data import IngestionService

        service = IngestionService(lakehouse_dir=temp_lakehouse, freshness_hours=12)
        service.ingest([{"symbol": symbol}])

        # Verify sync WAS called
        loader_instance.sync.assert_called_with(symbol, interval="1d", depth=ANY, total_timeout=ANY)


def test_toxic_data_filter(temp_lakehouse):
    """Test that toxic data (>500% return) is rejected."""
    symbol = "BINANCE:TOXIC"

    # Mock loader returning toxic data
    toxic_df = pd.DataFrame(
        {
            "timestamp": [1000, 2000],
            "close": [1.0, 10.0],  # 900% return
            "open": [1.0, 10.0],
            "high": [1.0, 10.0],
            "low": [1.0, 10.0],
            "volume": [100, 100],
        }
    )

    with patch("scripts.services.ingest_data.PersistentDataLoader") as MockLoaderClass:
        loader_instance = MockLoaderClass.return_value
        loader_instance.load.return_value = toxic_df

        from scripts.services.ingest_data import IngestionService

        service = IngestionService(lakehouse_dir=temp_lakehouse)
        service.ingest([{"symbol": symbol}])

        # Verify sync called
        loader_instance.sync.assert_called()

        # Verify file NOT written (because it's toxic)
        safe_sym = "BINANCE_TOXIC"
        p_path = temp_lakehouse / f"{safe_sym}_1d.parquet"
        assert not p_path.exists()


def test_input_candidates_json(temp_lakehouse):
    """Test loading candidates from JSON file."""
    candidates = [{"symbol": "BINANCE:SOLUSDT"}, {"symbol": "BINANCE:AVAXUSDT"}]
    c_path = temp_lakehouse / "candidates.json"
    with open(c_path, "w") as f:
        json.dump(candidates, f)

    with patch("scripts.services.ingest_data.PersistentDataLoader") as MockLoaderClass:
        from scripts.services.ingest_data import IngestionService

        service = IngestionService(lakehouse_dir=temp_lakehouse)
        service.process_candidate_file(c_path)

        assert MockLoaderClass.return_value.sync.call_count == 2


def test_sanitize_symbol_valid():
    """Test that valid symbols are sanitized correctly."""
    from tradingview_scraper.utils.security import SecurityUtils

    assert SecurityUtils.sanitize_symbol("BINANCE:BTCUSDT") == "BINANCE_BTCUSDT"
    assert SecurityUtils.sanitize_symbol("BINANCE-BTCUSDT") == "BINANCE-BTCUSDT"
    assert SecurityUtils.sanitize_symbol("BTCUSDT") == "BTCUSDT"


def test_sanitize_symbol_invalid():
    """Test that invalid symbols raise ValueError."""
    from tradingview_scraper.utils.security import SecurityUtils

    with pytest.raises(ValueError, match="Invalid symbol format"):
        SecurityUtils.sanitize_symbol("BINANCE:BTCUSDT; rm -rf /")
    with pytest.raises(ValueError, match="Invalid symbol format"):
        SecurityUtils.sanitize_symbol("BTC$USDT")


def test_path_traversal_protection(temp_lakehouse):
    """Test that path traversal attempts are caught."""
    from tradingview_scraper.utils.security import SecurityUtils

    # Note: sanitize_symbol will catch '..' via the regex first
    with pytest.raises(ValueError, match="Invalid symbol format"):
        SecurityUtils.get_safe_path(temp_lakehouse, "../../../etc/passwd")

    with pytest.raises(ValueError, match="Invalid symbol format"):
        SecurityUtils.get_safe_path(temp_lakehouse, "/etc/passwd")


def test_ingest_malicious_symbol(temp_lakehouse):
    """Test that ingest skips malicious symbols."""
    with patch("scripts.services.ingest_data.PersistentDataLoader") as MockLoaderClass:
        loader_instance = MockLoaderClass.return_value
        from scripts.services.ingest_data import IngestionService

        service = IngestionService(lakehouse_dir=temp_lakehouse)

        # Ingest a list with one valid and one malicious symbol
        service.ingest([{"symbol": "BINANCE:BTCUSDT"}, {"symbol": "../../../evil"}])

        # Should only sync the valid one
        loader_instance.sync.assert_called_once_with("BINANCE:BTCUSDT", interval="1d", depth=ANY, total_timeout=ANY)
