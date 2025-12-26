# Composite Alpha Ranking & Lead Asset Selection

This specification documents the mathematical framework used for identifying high-quality candidates and selecting the optimal instrument for implementation within a risk cluster.

## 1. Discovery Alpha (Top Universe Selection)

During the candidate discovery phase, symbols are ranked within their respective categories (e.g., US_STOCKS, BINANCE_PERP) to filter out "noisy" tickers.

### The Discovery Score Formula:
$$Alpha_{Discovery} = 0.4 \cdot Norm(\text{Value Traded}) + 0.4 \cdot Norm(ADX) + 0.2 \cdot Norm(\text{Volatility})$$

- **Liquidity (40%)**: Prioritizes assets with significant institutional participation.
- **Trend Strength (40%)**: Uses ADX to find assets in strong directional regimes.
- **Participation (20%)**: Favors assets with active volatility, indicating current market interest.

## 2. Execution Alpha (Lead Asset Selection)

Once assets are grouped into hierarchical risk buckets, the system must choose a single "Lead Asset" for execution to minimize implementation friction and maximize risk-adjusted quality.

### The Execution Rank Formula:
$$Alpha_{Execution} = 0.4 \cdot Norm(\text{Momentum}) + 0.3 \cdot Norm(\text{Stability}) + 0.3 \cdot Norm(\text{Convexity})$$

- **Momentum (40%)**: Annualized mean return. Favors assets currently outperforming their cluster peers.
- **Stability (30%)**: Annualized inverse volatility ($1/\sigma$). Favors the most stable venue or instrument within the correlated group.
- **Convexity (30%)**: Normalized Antifragility Score (Positive Skew + Tail Gain). Prioritizes assets with asymmetric upside potential.

## 3. Implementation Logic

- **Normalization**: Components are normalized within the cluster using min-max scaling to ensure metrics are comparable.
- **Venue Neutrality**: This framework naturally handles venue redundancy by picking the exchange or instrument type (Spot vs. Perp) that offers the best balance of trend strength and stability.
- **Automatic Fallback**: If convexity metrics are unavailable, the system defaults to a Momentum/Stability balance.
