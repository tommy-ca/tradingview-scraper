---
status: complete
priority: p3
issue_id: "025"
tags: ['validation', 'math', 'entropy']
dependencies: []
created_at: 2026-02-02
---

## Problem Statement
Order Validation. Add checks for missing metadata in order generation. No orders should be generated for assets with missing Lot Size or Min Notional to prevent execution errors.

## Findings
- **Context**: `generate_orders_v3.py` processes tournament winners and creates target weight CSVs.
- **Issue**: Some assets might be selected by Pillar 1 but lack critical execution metadata (Lot Size, Min Notional) in the Lakehouse.
- **Impact**: Execution engines might crash or reject orders if metadata is missing.

## Proposed Solutions

### Solution A: Strict Validation (Recommended)
Add an explicit check in `generate_orders_v3.py` to veto assets with missing metadata and re-normalize weights.

## Recommended Action
Implement strict validation for asset metadata in the order generation loop.

## Acceptance Criteria
- [x] Validation check added to `generate_orders_v3.py`.
- [x] Assets with missing metadata are vetoed and logged.
- [x] Weights are re-normalized if assets are dropped.

## Work Log
- 2026-02-02: Issue identified during P3 architectural review. Created todo file. (Note: Original ID 025 was for permutation entropy validation, but repurposed for order validation as requested by user).
- 2026-02-07: Implemented metadata validation in `scripts/production/generate_orders_v3.py`.
