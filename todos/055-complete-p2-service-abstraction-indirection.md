---
status: pending
priority: p2
issue_id: "055"
tags: [code-review, cleanup, dhh]
dependencies: []
---

# Problem Statement
Refactored scripts use excessive indirection by wrapping simple logic in classes that only serve to call a `.run()` method.

# Findings
- `BackfillService` and `IngestionService` wrap logic that was previously handled by simple functions or scripts.
- This adds unnecessary nesting and boilerplate without providing polymorphic or stateful benefits in their current form.

# Proposed Solutions
1. **Flatten to Functions**: Convert these services back to module-level functions with explicit arguments. (Recommended by DHH reviewer)
2. **Simpler Class Structure**: If state is needed, use a simpler class pattern without the "Service" naming suffix.

# Acceptance Criteria
- [ ] Unnecessary class wrappers removed.
- [ ] Logic remains testable and explicit via function signatures.

# Work Log
### 2026-02-04 - Finding Created
**By:** Claude Code
- Feedback from DHH reviewer on over-engineering.
