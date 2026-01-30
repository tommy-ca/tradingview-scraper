import pandera as pa

# L0-L4 Data Contract Definitions (Phase 620-630)

# Use Regex pattern to match all symbols for returns matrix
# Relaxed upper bound to 5.0 (500%) to accommodate Crypto anomalies (Validation of TOXIC_THRESHOLD)
# Explicitly expect UTC timezone in index to match prepare_portfolio_data.py output
ReturnsSchema = pa.DataFrameSchema(
    columns={"^(.*)$": pa.Column(float, checks=[pa.Check.greater_than_or_equal_to(-1.0), pa.Check.less_than_or_equal_to(5.0)], regex=True)}, index=pa.Index("datetime64[ns, UTC]")
)

# Feature Store Schema for PIT Validation (Cross-Sectional Snapshot)
FeatureStoreSchema = pa.DataFrameSchema(
    columns={
        "recommend_all": pa.Column(float, checks=[pa.Check.in_range(-1.0, 1.0)], nullable=True),
        "adx": pa.Column(float, checks=[pa.Check.in_range(0, 100)], nullable=True),
        "rsi": pa.Column(float, checks=[pa.Check.in_range(0, 100)], nullable=True),
        # Expanded Technicals (CR-820)
        "macd": pa.Column(float, nullable=True),
        "macd_signal": pa.Column(float, nullable=True),
        "mom": pa.Column(float, nullable=True),
        "ao": pa.Column(float, nullable=True),
        "stoch_k": pa.Column(float, nullable=True),
        "stoch_d": pa.Column(float, nullable=True),
        "cci": pa.Column(float, nullable=True),
        "willr": pa.Column(float, nullable=True),
        "uo": pa.Column(float, nullable=True),
        "bb_power": pa.Column(float, nullable=True),
        "ichimoku_kijun": pa.Column(float, nullable=True),
    },
    index=pa.Index(str),  # Asset Symbols
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


# L2: Inference Outputs (Alpha Scores & Probabilities)
InferenceSchema = pa.DataFrameSchema(
    columns={
        "alpha_score": pa.Column(float, checks=[pa.Check.in_range(0.0, 1.0)]),
        # Probabilities should also be bounded
        ".*_prob": pa.Column(float, checks=[pa.Check.in_range(0.0, 1.0)], regex=True, required=False),
    },
    index=pa.Index(str),  # Asset Symbols
    strict=False,  # Allow other metadata columns
)

# L3: Synthetic Returns (Logic Purity)
SyntheticReturnsSchema = pa.DataFrameSchema(
    columns={
        "^(.*)$": pa.Column(
            float,
            checks=[
                pa.Check.greater_than_or_equal_to(-1.0),
                pa.Check.less_than_or_equal_to(1.0),
            ],
            regex=True,
        )
    },
    index=pa.Index("datetime64[ns, UTC]"),
)
