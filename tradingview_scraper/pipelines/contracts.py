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


# =============================================================================
# Tier 1: Structural Schema (ReturnsSchema) - Long Format
# =============================================================================
# Validates the fundamental shape and types of the data in Long/Tidy format.
ReturnsSchema = pa.DataFrameSchema(
    columns={
        "date": pa.Column(pa.DateTime, coerce=True, required=True),
        "symbol": pa.Column(str, required=True),
        "returns": pa.Column(float, nullable=False, required=True),
    },
    # Reset index usually implies int index (RangeIndex).
    # Removed 'required=False' as it's not a valid argument for pa.Index constructor in some versions
    index=pa.Index(int),
    strict=False,
    name="ReturnsSchema_Tier1",
)


# =============================================================================
# Tier 2: Semantic/Audit Schema (AuditSchema)
# =============================================================================
# Enforces statistical validity and business logic invariants.
AuditSchema = pa.DataFrameSchema(
    columns={
        "date": pa.Column(pa.DateTime, coerce=True, required=True),
        "symbol": pa.Column(str, required=True),
        "returns": pa.Column(
            float,
            checks=[
                pa.Check.greater_than_or_equal_to(-1.0, error="Returns cannot be less than -100%"),
                pa.Check.less_than_or_equal_to(10.0, error="Returns exceed 1000% (Toxic Data)"),
            ],
        ),
    },
    checks=[
        # No Weekend Padding for TradFi
        pa.Check(
            lambda df: ~(_is_tradfi(df["symbol"]) & (df["date"].dt.dayofweek >= 5) & (df["returns"] == 0.0)),
            error="TradFi assets detected with zero-filled weekend returns (Padding)",
            name="no_weekend_padding_tradfi",
            # Removed groupby as the lambda operates on the full DataFrame vectorially
        )
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
    index=pa.Index(pa.DateTime),
    name="ReturnsMatrixSchema",
)

# Feature Store Schema for PIT Validation
FeatureStoreSchema = pa.DataFrameSchema(
    columns={
        "recommend_all": pa.Column(float, checks=[pa.Check.in_range(-1.0, 1.0)], nullable=True),
        "adx": pa.Column(float, checks=[pa.Check.in_range(0, 100)], nullable=True),
        "rsi": pa.Column(float, checks=[pa.Check.in_range(0, 100)], nullable=True),
    },
    index=pa.Index(pa.DateTime),
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
