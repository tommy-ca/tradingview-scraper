import pandas as pd
import numpy as np
from scipy.optimize import minimize
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("barbell_optimizer")

def calculate_diversification_ratio(weights, returns):
    """
    Max Diversification Ratio = (w^T * sigma) / sqrt(w^T * Cov * w)
    """
    volatilities = returns.std() * np.sqrt(252)
    cov_matrix = returns.cov() * 252
    
    weighted_vol = np.dot(weights, volatilities)
    port_vol = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
    
    if port_vol == 0: return 0
    return weighted_vol / port_vol

def core_objective(weights, returns):
    # We want to maximize DR, so minimize negative DR
    return -calculate_diversification_ratio(weights, returns)

def build_barbell_portfolio():
    # 1. Load Data
    returns = pd.read_pickle("data/lakehouse/portfolio_returns.pkl")
    returns = returns.loc[:, (returns != 0).any(axis=0)]
    
    with open("data/lakehouse/antifragility_stats.json", "r") as f:
        stats = pd.read_json(f)
    
    # 2. SELECTION: Identify the Barbell
    # Aggressors: Top 5 by Antifragility Score
    aggressors = stats.sort_values('Antifragility_Score', ascending=False).head(5)['Symbol'].tolist()
    
    # Core: Everything else (Low volatility preference)
    core_candidates = [s for s in returns.columns if s not in aggressors]
    core_returns = returns[core_candidates]
    
    logger.info(f"Building Barbell: {len(aggressors)} Aggressors, {len(core_candidates)} Core Assets")

    # 3. OPTIMIZE CORE (90% Weight)
    n_core = len(core_candidates)
    init_weights = np.array([1.0 / n_core] * n_core)
    bounds = tuple((0.0, 0.1) for _ in range(n_core)) # Max 10% per core asset
    constraints = ({'type': 'eq', 'fun': lambda w: np.sum(w) - 1.0})
    
    logger.info("Solving for Maximum Diversification in Core...")
    res_core = minimize(
        core_objective,
        init_weights,
        args=(core_returns,),
        method='SLSQP',
        bounds=bounds,
        constraints=constraints
    )
    
    # 4. ALLOCATE AGGRESSORS (10% Weight - Equal Split for simplicity)
    agg_weight = 0.10 / len(aggressors)
    
    # 5. MERGE RESULTS
    portfolio = []
    # Add Core (90% of total)
    for i, symbol in enumerate(core_candidates):
        portfolio.append({
            "Symbol": symbol,
            "Type": "CORE (Safe)",
            "Weight": res_core.x[i] * 0.90
        })
        
    # Add Aggressors (10% of total)
    for symbol in aggressors:
        portfolio.append({
            "Symbol": symbol,
            "Type": "AGGRESSOR (Antifragile)",
            "Weight": agg_weight
        })
        
    df = pd.DataFrame(portfolio).sort_values('Weight', ascending=False)
    
    print("\n" + "="*80)
    print("ANTIFRAGILE BARBELL PORTFOLIO (Taleb Strategy)")
    print("="*80)
    print(f"Structure: 90% Diverse Core | 10% Convex Aggressors")
    print(f"Core Diversification Ratio: {-res_core.fun:.4f}")
    
    print("\nTop 15 Allocations:")
    print(df.head(15).to_string(index=False))
    
    print("\n[Aggressor Bucket - Tail Gain Engines]")
    print(df[df['Type'] == 'AGGRESSOR (Antifragile)'].to_string(index=False))

    df.to_json("data/lakehouse/portfolio_barbell.json")
    print("\nSaved to data/lakehouse/portfolio_barbell.json")

if __name__ == "__main__":
    build_barbell_portfolio()
