# Specification: Quantitative Benchmark Standards (v1)

## 1. Objective
To establish mathematical gates for evaluating the robustness, fidelity, and stability of quantitative strategies. These metrics distinguish between "Lucky" strategies and institutional-grade "Robust" alphas.

## 2. Core Robustness Metrics

### 2.1 Temporal Fragility (Window Variance)
- **Metric**: Coefficient of Variation (CV) of Sharpe Ratios across test windows.
- **Formula**: $CV_{Sharpe} = \frac{\sigma(Sharpe_{windows})}{|\mu(Sharpe_{windows})|}$
- **Standard**:
    - **Robust (< 0.5)**: High consistency across regimes.
    - **Standard (0.5 - 1.5)**: Variable but reliable performance.
    - **Fragile (> 1.5)**: Strategy is "Lucky," driven by outlier windows.

### 2.2 Friction Alignment (Slippage Decay)
- **Metric**: Sharpe Decay Ratio.
- **Formula**: $Decay_{Friction} = 1 - \frac{Sharpe_{HighFidelity}}{Sharpe_{Idealized}}$
- **Standard**:
    - **Institutional (< 0.1)**: Structural alpha that survives high execution costs.
    - **Acceptable (0.1 - 0.3)**: Standard decay for high-turnover strategies.
    - **Brittle (> 0.3)**: Alpha is likely noise or micro-market arbitrage that won't survive friction.

### 2.3 Selection Stability (Jaccard Index)
- **Metric**: Jaccard Similarity of Universe Winners.
- **Formula**: $J(U_{t}, U_{t-1}) = \frac{|U_t \cap U_{t-1}|}{|U_t \cup U_{t-1}|}$
- **Standard**:
    - **Stable (> 0.7)**: High structural persistence in selection factors.
    - **Dynamic (0.3 - 0.7)**: Regime-adaptive selection.
    - **Chasing Noise (< 0.3)**: Selection logic is unstable and likely overfitted to local window volatility.

### 2.4 Quantified Antifragility (Convexity + Crisis Response)
Antifragility is measured at the **strategy** level using **out-of-sample (OOS)** daily returns, aggregated across all walk-forward windows. This avoids the noise of short per-window tails (e.g., 20d windows).

#### 2.4.1 Distribution Antifragility (Convexity Index)
- **Metric**: Right-tail convexity vs left-tail fragility.
- **Definitions** (defaults: $q=0.95$, $\epsilon=10^{-12}$):
    - $TailGain_q = \mathbb{E}[r_t \mid r_t > Q_q(r)]$
    - $TailLoss_q = |\mathbb{E}[r_t \mid r_t < Q_{1-q}(r)]|$
    - $TailAsym_q = \frac{TailGain_q}{TailLoss_q + \epsilon}$
    - $AF_{dist} = Skew(r) + \ln(TailAsym_q + \epsilon)$
- **Data requirement**:
    - Require $N \ge 100$ OOS observations and at least 10 samples in each tail bucket; otherwise mark as **Insufficient**.
- **Standard**:
    - **Strong Antifragile (>= 0.25)**: Positive skew + dominant right tail.
    - **Acceptable (0.0 - 0.25)**: Mild convexity; not structurally fragile.
    - **Fragile (< 0.0)**: Negative skew and/or left tail dominates.

#### 2.4.2 Stress-Response Antifragility (Crisis Alpha)
- **Metric**: Outperformance during market stress days.
- **Reference**: Use `market` baseline returns when available; otherwise fall back to `raw_pool_ew`, then `benchmark`.
- **Definitions** (defaults: $q_{stress}=0.10$):
    - Stress set: $S = \{t \mid b_t \le Q_{q_{stress}}(b)\}$ where $b_t$ is the reference baseline return.
    - Crisis alpha: $AF_{stress} = \mathbb{E}[r_t - b_t \mid t \in S]$
    - Stress delta: $\Delta_{stress} = \mathbb{E}[r_t - b_t \mid t \in S] - \mathbb{E}[r_t - b_t \mid t \notin S]$
- **Data requirement**:
    - Require at least 10 stress observations ($|S| \ge 10$); otherwise mark as **Insufficient**.
- **Standard**:
    - **Crisis-Resilient (>= 0)**: Beats the baseline on worst days.
    - **Stress-Antifragile (>= 0 and $\Delta_{stress} \ge 0$)**: Improves excess alpha in stress vs calm.
    - **Crisis-Fragile (< 0)**: Underperforms baseline during stress.

### 2.5 Market Sensitivity (Beta & Correlation)
- **Metric**: Sensitivity of strategy returns to the market baseline.
- **Reference**: Use `market` baseline returns when available; otherwise fall back to `AMEX:SPY` when present.
- **Formula**:
    - $\beta = \frac{Cov(R_{strategy}, R_{mkt})}{Var(R_{mkt})}$
    - $\rho = Corr(R_{strategy}, R_{mkt})$
- **Standard**:
    - **Defensive Gate (Min Variance)**: $\beta \le 0.5$ (otherwise flagged as aggressive).
    - **Interpretation**: High Sharpe with high $\beta$ is often hidden market exposure, not structural alpha.

### 2.6 Concentration & Diversification (HHI + Cluster Cap)
- **Metric**: Concentration of weights and correlated exposures.
- **Definitions**:
    - **HHI (Concentration)**: $HHI = \sum_i w_i^2$ (gross weights). Effective breadth: $N_{eff} = 1 / HHI$.
    - **Cluster Concentration**: $\max_{cluster}(\sum_{i \in cluster} w_i)$.
- **Standard**:
    - **Cluster Cap Gate**: $\max_{cluster} \le 0.25$ for profiles expected to respect `cluster_cap` (barbell aggressor sleeve is exempt).
    - **HHI Bands (Diagnostic)**:
        - **Diversified (<= 0.15)**: $N_{eff} \ge 6.7$ effective positions.
        - **Moderate (0.15 - 0.25)**: $N_{eff} \approx 4 - 6.7$.
        - **Concentrated (> 0.25)**: $N_{eff} < 4$.

### 2.7 Tail Risk Gate (CVaR + MDD)
- **Metric**: Left-tail loss severity and drawdown depth.
- **Definitions**:
    - $CVaR_{95} = \mathbb{E}[r_t \mid r_t \le Q_{0.05}(r)]$
    - $MDD = \min_t \left(\frac{Equity_t}{\max_{\tau \le t} Equity_{\tau}} - 1\right)$
- **Standard (Relative to `market`)**:
    - **Institutional (<= 1.25x baseline)**: $|CVaR_{95}^{strategy}| \le 1.25\,|CVaR_{95}^{mkt}|$ and $|MDD^{strategy}| \le 1.25\,|MDD^{mkt}|$.
    - **Fragile (> 1.25x baseline)**: Tail loss / drawdown materially worse than the market hurdle.

### 2.8 Turnover Efficiency (Churn)
- **Metric**: One-way turnover as a proxy for implementability drag.
- **Definition**: $Turnover = \sum |w_t - w_{t-1}| / 2$ (one-way).
- **Standard (within same tournament settings)**:
    - **Low Churn (<= 0.25)**: Institutional-friendly.
    - **Standard (0.25 - 0.50)**: Acceptable with friction-aware simulators.
    - **High Churn (> 0.50)**: Likely brittle unless alpha is strongly structural.

### 2.9 Simulator Parity (Implementation Fidelity)
- **Metric**: Divergence between independent high-fidelity simulators.
- **Standard**:
    - **Parity Gate**: Annualized return divergence between `cvxportfolio` and `nautilus` must be < 1.5% (when both are available).

### 2.10 Regime Robustness (Stress Windows)
- **Metric**: Worst-regime performance and crisis survivability.
- **Definition**:
    - $R_{worst\_regime} = \min_{regime}(\mathbb{E}[R_{window} \mid regime])$
- **Standard**:
    - **Robust Candidate**: Avoids catastrophic worst-regime collapses and does not rely on a single regime for profitability.

## 3. Implementation Workflow

1. **Tournament Execution**: Run multi-window backtests across all configurations.
2. **Forensic Audit**: Apply `scripts/research/audit_tournament_forensics.py` to calculate the robustness and antifragility metrics (requires audit ledger; antifragility is sourced from `backtest_summary`).
3. **Scoreboard + Candidate Filter**: Run `scripts/research/tournament_scoreboard.py` to generate `data/tournament_scoreboard.csv`, `data/tournament_candidates.csv`, and `reports/research/tournament_scoreboard.md`.
4. **Production Artifact Audit**: Run `scripts/validate_portfolio_artifacts.py` to enforce market sensitivity (beta), cluster concentration caps, and other post-optimization safety checks.
5. **Guardrail Gate**: Configurations failing the **Institutional** or **Robust** thresholds are flagged in the `INDEX.md` and excluded from the "Production Candidate" list.
