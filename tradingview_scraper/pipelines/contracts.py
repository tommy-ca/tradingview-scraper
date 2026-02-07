import pandera as pa
import pandas as pd
from typing import Optional

# Crypto exchanges for determining asset class
CRYPTO_EXCHANGES = ["BINANCE", "OKX", "BYBIT", "BITGET", "KUCOIN", "COINBASE", "KRAKEN"]


def _is_tradfi(symbol: pd.Series) -> pd.Series:
    """Returns boolean mask: True if symbol is TradFi (not in CRYPTO_EXCHANGES)."""

    def check_exchange(s):
        if ":" in str(s):
            exch = str(s).split(":")[0].upper()
            return exch not in CRYPTO_EXCHANGES
        return True

    return symbol.map(check_exchange)


def _get_field(df: pd.DataFrame, name: str) -> pd.Series:
    """Helper to get a series from columns or index level, ensuring index alignment."""
    if name in df.columns:
        return df[name]
    if name in df.index.names:
        # Convert index level to series to ensure consistent behavior (e.g. .dt accessor)
        return pd.Series(df.index.get_level_values(name), index=df.index, name=name)
    raise KeyError(f"Field '{name}' not found in columns or index levels {df.index.names}")


# =============================================================================
# Tier 1: Structural Schema (ReturnsSchema) - Long Format
# =============================================================================
# Validates the fundamental shape and types of the data in Long/Tidy format.
ReturnsSchema = pa.DataFrameSchema(
    columns={
        "date": pa.Column("datetime64[ns, UTC]", coerce=True, required=False),
        "symbol": pa.Column(str, required=False),
        "returns": pa.Column(float, nullable=False, required=True),
    },
    # Relaxed index to support RangeIndex, DatetimeIndex, and MultiIndex
    index=None,
    strict=False,
    checks=[
        pa.Check(lambda df: "date" in df.columns or "date" in df.index.names, name="date_present"),
        pa.Check(lambda df: "symbol" in df.columns or "symbol" in df.index.names, name="symbol_present"),
        pa.Check(
            lambda df: pd.api.types.is_datetime64tz_dtype(_get_field(df, "date")),
            name="date_is_utc",
            error="Date must be UTC-aware",
        ),
    ],
    name="ReturnsSchema_Tier1",
)


# =============================================================================
# Tier 2: Semantic/Audit Schema (AuditSchema)
# =============================================================================
# Enforces statistical validity and business logic invariants.
AuditSchema = pa.DataFrameSchema(
    columns={
        "date": pa.Column("datetime64[ns, UTC]", coerce=True, required=False),
        "symbol": pa.Column(str, required=False),
        "returns": pa.Column(
            float,
            checks=[
                pa.Check.greater_than_or_equal_to(-1.0, error="Returns cannot be less than -100%"),
                pa.Check.less_than_or_equal_to(10.0, error="Returns exceed 1000% (Toxic Data)"),
            ],
        ),
    },
    index=None,
    checks=[
        # No Weekend Padding for TradFi
        pa.Check(
            lambda df: ~(_is_tradfi(_get_field(df, "symbol")) & (_get_field(df, "date").dt.dayofweek >= 5) & (df["returns"] == 0.0)),
            error="TradFi assets detected with zero-filled weekend returns (Padding)",
            name="no_weekend_padding_tradfi",
        ),
        # Ensure field presence and UTC awareness
        pa.Check(lambda df: "date" in df.columns or "date" in df.index.names, name="date_present"),
        pa.Check(lambda df: "symbol" in df.columns or "symbol" in df.index.names, name="symbol_present"),
        pa.Check(
            lambda df: pd.api.types.is_datetime64tz_dtype(_get_field(df, "date")),
            name="date_is_utc",
            error="Date must be UTC-aware",
        ),
    ],
    name="AuditSchema_Tier2",
)

# =============================================================================
# Legacy/Wide Schemas (Preserved for backward compatibility)
# =============================================================================

# L0: Returns Matrix (Wide Format)
# Used by IngestionValidator and legacy pipelines
ReturnsMatrixSchema = pa.DataFrameSchema(
    columns={
        "^(.*)$": pa.Column(
            float,
            checks=[
                pa.Check.greater_than_or_equal_to(-1.0),
                pa.Check.less_than_or_equal_to(1.0),  # L0 invariant: |r| <= 1.0 (Strict)
            ],
            regex=True,
        )
    },
    index=pa.Index("datetime64[ns, UTC]", coerce=True),
    name="ReturnsMatrixSchema",
)

# Feature Store Schema for PIT Validation
FeatureStoreSchema = pa.DataFrameSchema(
    columns={
        "recommend_all": pa.Column(float, checks=[pa.Check.in_range(-1.0, 1.0)], nullable=True),
        "adx": pa.Column(float, checks=[pa.Check.in_range(0, 100)], nullable=True),
        "rsi": pa.Column(float, checks=[pa.Check.in_range(0, 100)], nullable=True),
    },
    index=pa.Index("datetime64[ns, UTC]", coerce=True),
    strict=False,  # Allow other technical features
)

WeightsSchema = pa.DataFrameSchema(
    columns={
        "Symbol": pa.Column(str),
        "Weight": pa.Column(float, checks=[pa.Check.greater_than_or_equal_to(0.0), pa.Check.less_than_or_equal_to(1.0)]),
        "Net_Weight": pa.Column(float, required=False),
    },
    checks=[
        # Simplex constraint (Sum of absolute weights <= 1.0 + tolerance)
        pa.Check(lambda df: df["Weight"].sum() <= 1.05, name="simplex_sum_constraint")
    ],
)
