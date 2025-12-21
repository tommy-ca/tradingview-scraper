import logging
import os
from typing import Dict, List, Optional

import pandas as pd

logger = logging.getLogger(__name__)

# Canonical metadata for common exchanges
DEFAULT_EXCHANGE_METADATA = {
    "BINANCE": {"timezone": "UTC", "is_crypto": True, "country": "Global"},
    "OKX": {"timezone": "UTC", "is_crypto": True, "country": "Global"},
    "BYBIT": {"timezone": "UTC", "is_crypto": True, "country": "Global"},
    "BITGET": {"timezone": "UTC", "is_crypto": True, "country": "Global"},
    "NASDAQ": {"timezone": "America/New_York", "is_crypto": False, "country": "United States"},
    "NYSE": {"timezone": "America/New_York", "is_crypto": False, "country": "United States"},
    "CME": {"timezone": "America/Chicago", "is_crypto": False, "country": "United States"},
    "CME_MINI": {"timezone": "America/Chicago", "is_crypto": False, "country": "United States"},
    "CBOT": {"timezone": "America/Chicago", "is_crypto": False, "country": "United States"},
    "COMEX": {"timezone": "America/Chicago", "is_crypto": False, "country": "United States"},
    "NYMEX": {"timezone": "America/Chicago", "is_crypto": False, "country": "United States"},
    "ICE": {"timezone": "America/New_York", "is_crypto": False, "country": "United States"},
    "LSE": {"timezone": "Europe/London", "is_crypto": False, "country": "United Kingdom"},
    "FX_IDC": {"timezone": "UTC", "is_crypto": False, "country": "Global"},
}


class MetadataCatalog:
    """
    Manages the symbol metadata catalog for the Data Lakehouse.

    Acts as the single source of truth for instrument definitions,
    providing lookup and search capabilities.
    """

    def __init__(self, base_path: str = "data/lakehouse"):
        self.base_path = base_path
        self.catalog_path = os.path.join(self.base_path, "symbols.parquet")
        os.makedirs(self.base_path, exist_ok=True)
        self._df = self._load_catalog()

    def _load_catalog(self) -> pd.DataFrame:
        """Loads the catalog from disk or returns an empty DataFrame."""
        if os.path.exists(self.catalog_path):
            try:
                return pd.read_parquet(self.catalog_path)
            except Exception as e:
                logger.error(f"Failed to load metadata catalog: {e}")

        # Initialize with standard schema including PIT and enriched fields
        cols: List[str] = [
            "symbol",
            "exchange",
            "base",
            "quote",
            "type",
            "subtype",
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
        return pd.DataFrame(data=None, columns=pd.Index(cols))

    def upsert_symbols(self, symbols_data: List[Dict]):
        """
        Inserts or updates multiple symbol definitions using SCD Type 2.
        """
        if not symbols_data:
            return

        now_ts = pd.Timestamp.now()
        new_records = []
        updates_mask = pd.Series(False, index=self._df.index)

        # Convert input to map for easy lookup
        incoming_map = {item["symbol"]: item for item in symbols_data}

        # 1. Process existing active symbols
        for idx, row in self._df[self._df["valid_until"].isna()].iterrows():
            sym = row["symbol"]
            if sym in incoming_map:
                new_data = incoming_map[sym]
                # Check for changes (simplified: check if any key field differs)
                # For now, we assume if it's passed in, we might want to update it.
                # A real impl would compare specific fields.
                # Let's assume we always update if present for this prototype.

                # Retire old record
                self._df.at[idx, "valid_until"] = now_ts

                # Prepare new record
                record = new_data.copy()
                record["valid_from"] = now_ts
                record["valid_until"] = None
                record["updated_at"] = now_ts
                new_records.append(record)

                # Remove from incoming map so we don't double insert
                del incoming_map[sym]

        # 2. Process completely new symbols
        for sym, data in incoming_map.items():
            record = data.copy()
            record["valid_from"] = now_ts
            record["valid_until"] = None
            record["updated_at"] = now_ts
            new_records.append(record)

        # 3. Append new records
        if new_records:
            self._df = pd.concat([self._df, pd.DataFrame(new_records)], ignore_index=True)

        self.save()

    def retire_symbols(self, symbols: List[str]):
        """
        Marks symbols as inactive and ends their validity window using SCD Type 2.
        """
        if not symbols:
            return

        now_ts = pd.Timestamp.now()
        new_records = []

        # Find active records for these symbols
        mask = (self._df["symbol"].isin(symbols)) & (self._df["valid_until"].isna())

        for idx, row in self._df[mask].iterrows():
            # 1. Expire the old record
            self._df.at[idx, "valid_until"] = now_ts

            # 2. Create a new "Inactive" record for the future
            record = row.to_dict()
            record["active"] = False
            record["valid_from"] = now_ts
            record["valid_until"] = None
            record["updated_at"] = now_ts
            new_records.append(record)

        if new_records:
            self._df = pd.concat([self._df, pd.DataFrame(new_records)], ignore_index=True)
            self.save()
            logger.info(f"Retired {len(new_records)} symbols. New inactive versions created.")

    def get_instrument(self, symbol: str, as_of: Optional[float] = None) -> Optional[Dict]:
        """
        Retrieves metadata for a specific symbol.

        Args:
            symbol: The symbol to look up.
            as_of: Optional timestamp (float or datetime) for Point-in-Time lookup.
                   If None, returns the current active record.
        """
        if self._df.empty:
            return None

        # Base filter by symbol
        mask = self._df["symbol"] == symbol

        if as_of is None:
            # Get currently active
            mask &= self._df["valid_until"].isna()
        else:
            # PIT lookup
            ts = pd.Timestamp(as_of)
            mask &= (self._df["valid_from"] <= ts) & ((self._df["valid_until"].isna()) | (self._df["valid_until"] > ts))

        match = self._df[mask]
        if match.empty:
            return None

        return match.iloc[0].to_dict()

    def list_active_symbols(self, exchange: Optional[str] = None) -> List[str]:
        """Returns a list of active symbols, optionally filtered by exchange."""
        if self._df.empty:
            return []

        query = self._df[self._df["active"] == True]
        if exchange:
            query = query[query["exchange"] == exchange]

        return query["symbol"].tolist()

    def save(self):
        """Persists the catalog to disk."""
        self._df.to_parquet(self.catalog_path, index=False)
        logger.info(f"Metadata catalog saved with {len(self._df)} entries.")


class ExchangeCatalog:
    """
    Manages the exchange metadata catalog for the Data Lakehouse.
    """

    def __init__(self, base_path: str = "data/lakehouse"):
        self.base_path = base_path
        self.catalog_path = os.path.join(self.base_path, "exchanges.parquet")
        os.makedirs(self.base_path, exist_ok=True)
        self._df = self._load_catalog()

    def _load_catalog(self) -> pd.DataFrame:
        """Loads the catalog from disk or returns an empty DataFrame."""
        if os.path.exists(self.catalog_path):
            try:
                return pd.read_parquet(self.catalog_path)
            except Exception as e:
                logger.error(f"Failed to load exchange catalog: {e}")

        cols: List[str] = ["exchange", "country", "timezone", "is_crypto", "description", "updated_at"]
        return pd.DataFrame(data=None, columns=pd.Index(cols))

    def upsert_exchange(self, exchange_data: Dict):
        """Inserts or updates an exchange definition."""
        name = exchange_data.get("exchange")
        if not name:
            return

        new_row = exchange_data.copy()
        new_row["updated_at"] = pd.Timestamp.now()
        new_df = pd.DataFrame([new_row])

        if self._df.empty:
            self._df = new_df
        else:
            self._df = pd.concat([self._df, new_df]).drop_duplicates(subset=["exchange"], keep="last")

        self.save()

    def get_exchange(self, exchange: str) -> Optional[Dict]:
        """Retrieves metadata for a specific exchange."""
        if self._df.empty:
            return None
        match = self._df[self._df["exchange"] == exchange]
        return match.iloc[0].to_dict() if not match.empty else None

    def save(self):
        """Persists the catalog to disk."""
        self._df.to_parquet(self.catalog_path, index=False)
        logger.info(f"Exchange catalog saved with {len(self._df)} entries.")


class MetadataService:
    """
    Higher-level service for interacting with the Metadata Catalog.
    Will eventually handle hybrid sourcing (TV + CCXT).
    """

    def __init__(self, catalog: Optional[MetadataCatalog] = None):
        self.catalog = catalog or MetadataCatalog()

    def resolve_symbol(self, symbol: str) -> Dict:
        """
        Attempts to find metadata for a symbol.
        If missing, this would be where 'Discovery' is triggered.
        """
        meta = self.catalog.get_instrument(symbol)
        if meta:
            return meta

        # TODO: Trigger discovery/enrichment if symbol is unknown
        return {"symbol": symbol, "error": "Not in catalog"}
