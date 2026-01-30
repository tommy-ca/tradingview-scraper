import os
import sys
import time
from unittest.mock import ANY, patch

import pandas as pd
import pytest

sys.path.append(os.getcwd())


@pytest.fixture
def temp_lakehouse(tmp_path):
    lake_dir = tmp_path / "data" / "lakehouse"
    lake_dir.mkdir(parents=True)
    return lake_dir


def test_zero_sync_on_stale_file_is_failure(temp_lakehouse):
    """Test that if sync returns 0 for a stale file, it is marked as stale/failed, not healthy."""
    symbol = "BINANCE:BTCUSDT"
    safe_sym = "BINANCE_BTCUSDT"

    # Create a stale file
    p_path = temp_lakehouse / f"{safe_sym}_1d.parquet"
    pd.DataFrame({"close": [1]}).to_parquet(p_path)
    stale_time = time.time() - (168 * 3600 + 100)  # > 168h
    os.utime(p_path, (stale_time, stale_time))

    with patch("scripts.services.ingest_data.PersistentDataLoader") as MockLoaderClass:
        loader_instance = MockLoaderClass.return_value
        # Mock sync to return 0 records
        loader_instance.sync.return_value = 0

        from scripts.services.ingest_data import IngestionService

        service = IngestionService(lakehouse_dir=temp_lakehouse, freshness_hours=12)
        service.ingest([{"symbol": symbol}])

        # Verify registry entry
        # If it returns 0, it should NOT be "healthy"
        status = service.registry.data.get(symbol, {}).get("status")
        assert status != "healthy", f"Expected non-healthy status for zero sync, got {status}"
        assert status == "stale" or status == "failed"
