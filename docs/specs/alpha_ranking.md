# Composite Alpha Ranking & Lead Asset Selection

This specification documents the mathematical framework used for identifying high-quality candidates and selecting the optimal instrument for implementation within a risk cluster.

## 1. Discovery Alpha (Tiered Selection Stage 1)

During the candidate discovery phase, symbols are ranked to filter out "noisy" tickers. The system implements a **Direction-Aware Discovery Gate** to ensure high-conviction candidates enter the backfill queue.

### The Discovery Score Formula:
$$Alpha_{Discovery} = 0.3 \cdot Norm(\text{Value Traded}) + 0.3 \cdot Norm(ADX) + 0.1 \cdot Norm(\text{Volatility}) + 0.3 \cdot Norm(\text{Performance})$$

- **Liquidity (30%)**: Prioritizes assets with significant institutional participation ($1B+ for Stocks, $50M+ for ETFs).
- **Trend Strength (30%)**: Uses ADX to find assets in strong directional regimes.
- **Participation (10%)**: Favors assets with active volatility, indicating current market interest.
- **Performance (30%)**: Direction-aware metric. 
    - For **LONG** candidates: $Norm(\text{Perf.3M} + \text{Perf.6M})$
    - For **SHORT** candidates: $Norm(-(\text{Perf.3M} + \text{Perf.6M}))$

## 2. Execution Alpha (Lead Asset Selection)

Once assets are grouped into hierarchical risk buckets, the system must choose a single "Lead Asset" for execution to minimize implementation friction and maximize risk-adjusted quality.

### The Execution Rank Formula:
$$Alpha_{Execution} = 0.4 \cdot Norm(\text{Momentum}) + 0.3 \cdot Norm(\text{Stability}) + 0.3 \cdot Norm(\text{Convexity})$$

- **Momentum (40%)**: Annualized mean return. Favors assets currently outperforming their cluster peers.
- **Stability (30%)**: Annualized inverse volatility ($1/\sigma$). Favors the most stable venue or instrument within the correlated group.
- **Convexity (30%)**: Normalized Antifragility Score (Positive Skew + Tail Gain). Prioritizes assets with asymmetric upside potential.

## 3. Implementation Logic

- **Normalization**: Components are normalized within the cluster using min-max scaling.
- **Venue Neutrality**: Redundant venues (e.g. BTC on Binance vs OKX) compete statistically. The winner becomes the `Lead Asset`, while others are preserved as `Implementation Alts`.
- **Intra-Cluster Hedging**: The selection engine picks the **Top LONG** and **Top SHORT** per bucket if available, allowing for factor-neutral relative value trades.
