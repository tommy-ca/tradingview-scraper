import numpy as np
import pandas as pd

from tradingview_scraper.portfolio_engines.base import EngineRequest
from tradingview_scraper.portfolio_engines.impl.custom import CustomClusteredEngine
from tradingview_scraper.utils.synthesis import calculate_beta


def test_market_neutral_beta_constraint():
    np.random.seed(42)
    # Benchmark returns
    bench_rets = pd.Series(np.random.normal(0.01, 0.01, 200))

    # Asset A: Beta ~ 2.0, high positive drift
    rets_a = 2.0 * bench_rets + np.random.normal(0.01, 0.005, 200)
    # Asset B: Beta ~ 0.5, small positive drift
    rets_b = 0.5 * bench_rets + np.random.normal(0.001, 0.005, 200)
    # Asset C: Beta ~ -1.5, negative drift
    rets_c = -1.5 * bench_rets + np.random.normal(-0.01, 0.005, 200)

    returns = pd.DataFrame({"BETA_HIGH": rets_a, "BETA_LOW": rets_b, "BETA_NEG": rets_c, "BENCH": bench_rets})

    clusters = {"1": ["BETA_HIGH"], "2": ["BETA_LOW"], "3": ["BETA_NEG"]}
    meta = {s: {"symbol": s, "direction": "LONG"} for s in returns.columns}

    engine = CustomClusteredEngine()

    # 1. Unconstrained - using a large cap to ensure feasibility
    req_un = EngineRequest(profile="max_sharpe", market_neutral=False, cluster_cap=0.8)
    resp_un = engine.optimize(returns=returns, clusters=clusters, meta=meta, request=req_un)
    w_un = resp_un.weights.set_index("Symbol")["Weight"]

    # 2. Neutral - using a large cap to allow hedging
    req_neu = EngineRequest(profile="max_sharpe", market_neutral=True, benchmark_returns=returns["BENCH"], cluster_cap=0.8)
    resp_neu = engine.optimize(returns=returns, clusters=clusters, meta=meta, request=req_neu)
    w_neu = resp_neu.weights.set_index("Symbol")["Weight"]

    beta_a = calculate_beta(returns["BETA_HIGH"], returns["BENCH"])
    beta_b = calculate_beta(returns["BETA_LOW"], returns["BENCH"])
    beta_c = calculate_beta(returns["BETA_NEG"], returns["BENCH"])

    pb_un = w_un.get("BETA_HIGH", 0) * beta_a + w_un.get("BETA_LOW", 0) * beta_b + w_un.get("BETA_NEG", 0) * beta_c
    pb_neu = w_neu.get("BETA_HIGH", 0) * beta_a + w_neu.get("BETA_LOW", 0) * beta_b + w_neu.get("BETA_NEG", 0) * beta_c

    print(f"\nBetas: A={beta_a:.2f}, B={beta_b:.2f}, C={beta_c:.2f}")
    print(f"Unconstrained Weights: {w_un.to_dict()}")
    print(f"Neutral Weights: {w_neu.to_dict()}")
    print(f"Port Beta Un: {pb_un:.4f}")
    print(f"Port Beta Neu: {pb_neu:.4f}")

    assert abs(pb_neu) <= 0.16  # matched to our internal tolerance of 0.15
    assert abs(pb_neu) < abs(pb_un)
