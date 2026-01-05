# Production Pipeline Status + Expansion Roadmap (Jan 5, 2026)

This document is a snapshot review of the current production pipeline readiness and a plan to expand discovery/universe coverage via multi-perspective “atoms” (assets, ETFs, strategies, smart-money portfolios).

## 1) Production Pipeline Status (as of 2026-01-05)

### What is working (validated recently)
- **Manifest-driven workflow**: `make flow-production PROFILE=production` is manifest-resolved via `tradingview_scraper.settings` (`docs/specs/workflow_manifests.md`).
- **Composable discovery pipelines**: `make scan-run` uses layered scanner composition (`docs/specs/pipeline_composition.md`).
- **Selection engines**: v3.2 (Log-MPS) is formalized as the preferred selection standard (`docs/specs/selection_intelligence_v1.md`, `docs/specs/universe_selection_v3_fp.md`).
- **Strict-scoreboard gates**: tournament scoreboard + strict candidates are stable and auditable; baselines are present and now treated as reference rows in ranking outputs.
- **Audit ledger integrity**: `audit.jsonl` is cryptographically hash-chained and verified as part of run review.

### Known blockers / risks for “production-ready”
These do not negate correctness, but they are the items that typically prevent a “ready for production” declaration:

1. **Selected-universe strict health failures due to STALE symbols**
   - Some selected assets can be stale (especially crypto venue symbols), causing `make data-audit STRICT_HEALTH=1` to fail.
   - This is operationally blocking because strict health is an institutional hard gate.

2. **Simulator parity gate realism**
   - When both `cvxportfolio` and `nautilus` are present, `parity_ann_return_gap` can be non-trivial.
   - Until the Nautilus integration is fully independent (vs parity proxy), parity may remain a top veto in some grids and reduce strict candidates.

3. **Scanner breadth limitations**
   - Discovery still tends to be equity/crypto heavy unless explicitly expanded.
   - Narrow discovery can create correlation redundancy and reduce the value of clustering + selection.

## 2) Expansion Objective
Expand discovery and portfolio construction breadth-first by introducing multiple **perspectives** represented as **atoms**:
- **Instrument atoms** (existing),
- **ETF proxy atoms** (next; easiest),
- **Strategy atoms** (research-first; derived from tournament results),
- **Smart-money portfolio atoms** (research-first; ingestion-dependent).

Key principle:
- We expand *coverage* without weakening strict production gates.
- Research-only diagnostics can exist, but they must not silently veto/admit candidates unless explicitly promoted into thresholded gates.

Spec reference:
- `docs/specs/universe_atoms_and_perspectives_v1.md`

## 3) Proposed Breadth-First Roadmap (phased)

### Phase A — ETF proxy sleeve (production-parity)
Deliverables:
- Canonical ETF proxy baskets per asset type (small lists).
- Scanner/discovery path emits these as atoms with tags (`asset_type`, `region`, `subclass`).
- Run production-parity mini-matrix smokes and confirm:
  - strict candidates are non-empty (non-baseline),
  - baseline reference rows are present and auditable,
  - health audit passes for the selected ETF sleeve.

### Phase B — Asset-type scanners breadth-first (production-parity)
Deliverables:
- Expand discovery pipelines to include at least one slice each:
  - equities (US + ex-US),
  - bonds/rates,
  - commodities,
  - FX,
  - crypto majors,
  - REIT proxy.
- Ensure metadata tagging is present so clustering can reason across categories.

### Phase C — Multi-sleeve meta-portfolio (production, after health gates are stable)
Deliverables:
- Allocate within each sleeve (instrument sleeve, ETF sleeve).
- Allocate across sleeves at the top level (HRP on sleeve return streams).
- Maintain strict scoreboard as the tournament-level gating for strategy configurations.

### Phase D — Strategy universe (research)
Deliverables:
- Treat each (selection, rebalance, engine, profile, simulator) as a “strategy atom”.
- Build a strategy returns matrix from tournament return pickles.
- Cluster strategies and measure:
  - diversification benefit,
  - robustness under strict-scoreboard gates,
  - regime-conditional fragility / sign-flip behavior.

### Phase E — Smart-money portfolios (research)
Deliverables:
- Deterministic ingestion (input data archived, hashes in ledger).
- Atom registry rows for portfolios + returns series construction policy.
- Research evaluation only until data quality and reproducibility are proven.

### Phase F — Promotion to Live Trading Platforms (production, gated)
Deliverables:
- Deterministic order generation from validated portfolio artifacts.
- Paper trading / shadow execution burn-in with full telemetry.
- Live trading adapters and risk controls per venue class.

Spec:
- `docs/specs/live_trading_promotion_pipeline_v1.md`

## 4) Acceptance Gates (institutional)
- A production-parity mini-matrix smoke produces non-empty strict candidates (non-baseline).
- `make data-audit STRICT_HEALTH=1` passes for the selected universe of the run.
- Audit ledger is verified and includes the artifacts needed for strict-scoreboard metrics.
- Multi-perspective additions do not blur calendar integrity (no weekend padding for TradFi).
