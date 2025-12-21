import json
import logging

import numpy as np
import pandas as pd
from scipy.optimize import minimize

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mpt_optimizer")


def calculate_portfolio_stats(weights, returns):
    cov_matrix = returns.cov() * 252
    port_variance = np.dot(weights.T, np.dot(cov_matrix, weights))
    port_volatility = np.sqrt(port_variance)
    return port_volatility


def min_variance_objective(weights, returns):
    return calculate_portfolio_stats(weights, returns)


def risk_parity_objective(weights, returns):
    cov_matrix = returns.cov() * 252
    port_vol = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))

    # Marginal Risk Contribution
    mrc = np.dot(cov_matrix, weights) / port_vol
    # Risk Contribution
    rc = weights * mrc

    # Target Risk Contribution (Equal for all)
    target_rc = port_vol / len(weights)

    # Sum of squared differences
    return np.sum(np.square(rc - target_rc))


def optimize_portfolio():
    # 1. Load Data
    returns = pd.read_pickle("data/lakehouse/portfolio_returns.pkl")
    with open("data/lakehouse/portfolio_meta.json", "r") as f:
        meta = json.load(f)

    # Filter for symbols that actually have enough data (avoid columns with all zeros/nans)
    returns = returns.loc[:, (returns != 0).any(axis=0)]
    n_assets = returns.shape[1]

    logger.info(f"Optimizing for {n_assets} assets...")

    # Initial weights
    init_weights = np.array([1.0 / n_assets] * n_assets)
    bounds = tuple((0.0, 1.0) for _ in range(n_assets))
    constraints = {"type": "eq", "fun": lambda w: np.sum(w) - 1.0}

    # 2. Optimization: MIN VARIANCE
    logger.info("Solving Minimum Variance Portfolio...")
    res_mv = minimize(min_variance_objective, init_weights, args=(returns,), method="SLSQP", bounds=bounds, constraints=constraints)

    # 3. Optimization: RISK PARITY
    logger.info("Solving Risk Parity Portfolio...")
    # Note: Risk parity constraint is just sum(weights)=1 and w > 0
    res_rp = minimize(risk_parity_objective, init_weights, args=(returns,), method="SLSQP", bounds=bounds, constraints=constraints)

    # 4. Results Formatting
    results_df = pd.DataFrame(index=returns.columns)
    results_df["Min_Var_Weight"] = res_mv.x
    results_df["Risk_Parity_Weight"] = res_rp.x

    # Metadata map for direction
    meta_map = {m["symbol"]: m["direction"] for m in meta}
    results_df["Signal"] = [meta_map.get(s, "UNKNOWN") for s in results_df.index]

    # Filter for non-zero weights (> 0.1%)
    mv_top = results_df[results_df["Min_Var_Weight"] > 0.001].sort_values("Min_Var_Weight", ascending=False)
    rp_top = results_df[results_df["Risk_Parity_Weight"] > 0.001].sort_values("Risk_Parity_Weight", ascending=False)

    print("\n" + "=" * 80)
    print("PORTFOLIO OPTIMIZATION RESULTS (MPT)")
    print("=" * 80)

    print(f"\n[1] MINIMUM VARIANCE PORTFOLIO (Expected Vol: {res_mv.fun:.2%})")
    print(mv_top[["Signal", "Min_Var_Weight"]].head(15).to_string())

    print("\n[2] RISK PARITY PORTFOLIO")
    print(rp_top[["Signal", "Risk_Parity_Weight"]].head(15).to_string())

    # Portfolio Metadata for Display
    port_stats = {"min_var_vol": float(res_mv.fun), "asset_count": n_assets}
    with open("data/lakehouse/portfolio_optimized.json", "w") as f:
        results_df.to_json(f)


if __name__ == "__main__":
    optimize_portfolio()
