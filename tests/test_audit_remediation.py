from unittest.mock import patch

import pandas as pd
import pytest

# Import the script's function
from scripts.cleanup_metadata_catalog import cleanup_metadata_catalog


@pytest.fixture
def mock_catalogs(tmp_path):
    """Sets up mock MetadataCatalog and ExchangeCatalog with temporary paths."""
    with patch("scripts.cleanup_metadata_catalog.MetadataCatalog") as MockMeta, patch("scripts.cleanup_metadata_catalog.ExchangeCatalog") as MockEx:
        # Mock MetadataCatalog
        meta_inst = MockMeta.return_value
        meta_inst._df = pd.DataFrame(
            columns=[
                "symbol",
                "exchange",
                "base",
                "quote",
                "type",
                "subtype",
                "profile",
                "description",
                "sector",
                "industry",
                "country",
                "pricescale",
                "minmov",
                "tick_size",
                "lot_size",
                "contract_size",
                "timezone",
                "session",
                "active",
                "updated_at",
                "valid_from",
                "valid_until",
            ]
        )

        # Mock ExchangeCatalog
        ex_inst = MockEx.return_value
        ex_inst._df = pd.DataFrame(columns=["exchange", "country", "timezone", "is_crypto", "description", "updated_at"])
        ex_inst.get_exchange.side_effect = lambda name: None  # Simulate FOREX missing

        yield MockMeta, MockEx, meta_inst, ex_inst


def test_cleanup_metadata_catalog_injects_forex(mock_catalogs):
    """Test that cleanup_metadata_catalog injects FOREX metadata if missing."""
    MockMeta, MockEx, meta_inst, ex_inst = mock_catalogs

    # We need to mock ExchangeCatalog within the script's execution context if it's imported there
    # or ensure cleanup_metadata_catalog uses it.
    # Looking at cleanup_metadata_catalog.py, it doesn't currently use ExchangeCatalog.
    # This test WILL FAIL until we implement the requirement.

    cleanup_metadata_catalog()

    # Verify that upsert_exchange was called with FOREX
    calls = [call for call in ex_inst.upsert_exchange.call_args_list if call.args[0]["exchange"] == "FOREX"]
    assert len(calls) > 0, "FOREX metadata was not injected into ExchangeCatalog"

    forex_data = calls[0].args[0]
    assert forex_data["timezone"] == "America/New_York"
    assert forex_data["is_crypto"] is False
