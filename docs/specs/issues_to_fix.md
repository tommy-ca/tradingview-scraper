# 🛠️ Quantitative Platform: Issues & Fixes

## ✅ Recently Fixed
- [x] **Selection Metadata Enrichment**: `scripts/enrich_candidates_metadata.py` now automatically detects and enriches the full returns universe with institutional defaults (`tick_size`, `lot_size`, etc.).
- [x] **Audit Ledger Hashing**: `tradingview_scraper/utils/audit.py` now handles mixed-type DataFrames (strings/floats) correctly.
- [x] **CVXPortfolio Simulator Fidelity**: Strictly aligned weight indices with rolling returns and standardized on `cash` modeling to prevent solver crashes.
- [x] **Dynamic Strategy Resume**: `scripts/generate_reports.py` now automatically identifies and highlights the best engine per profile in the strategy resume.
- [x] **Regime-Specific Attribution**: Fixed data loading priority in `generate_reports.py` to ensure window-level regime metrics are captured from `tournament_results.json`.
- [x] **Atomic & Safe Audit Writes**: Implemented Unix file locking (`fcntl`) in `scripts/natural_selection.py` to prevent corruption of the shared `selection_audit.json`.

## ⏳ High Priority: Remaining Logic Integrity
- [ ] **Standardize `run_selection` API**: Ensure all internal calls use a consistent 5-tuple return or a typed `SelectionResponse` object.
- [ ] **Alpha Isolation Baseline**: Ensure the `market` engine is automatically included in tournament runs if `alpha_isolation_audit.md` is requested.

## 📈 Medium Priority: Enhancements
- [ ] **Solver Dampening**: Add numerical regularizers to `cvxportfolio` to prevent "Variable value must be real" failures when encountering extreme survivorship bias winners (e.g., highly volatile crypto).
- [ ] **Automated RUN_ID Detection**: Report generator currently auto-detects, but could be smarter about identifying the *last finished* run vs just the last created directory.

## 📋 Technical Debt
- [ ] **Typed Settings**: Move more environment-variable based flags into the `pydantic` settings model.
- [ ] **Nautilus Full Integration**: Complete the event-driven strategy adapter for `NautilusSimulator`.
