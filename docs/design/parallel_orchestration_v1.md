# Design Specification: Multi-Sleeve Parallelization (v1.0)

## 1. Problem Statement
The current meta-portfolio production flow executes atomic sleeves sequentially. For complex meta-portfolios with 4+ sleeves, this leads to total runtimes of 10-20 minutes, even with bi-weekly steps. Independent sleeves (e.g., Long All and Short All) should be executed in parallel to utilize multicore resources.

## 2. Proposed Architecture

### 2.1 Parallel Orchestrator
- **Mechanism**: Use `concurrent.futures.ProcessPoolExecutor` in `scripts/run_meta_pipeline.py`.
- **Target**: The "Sleeve Execution" phase (Pillar 2).
- **Concurrency Limit**: Default to `min(N_sleeves, CPU_COUNT - 1)`.

### 2.2 Resource Management
- **File Locking**: Continue using `filelock` for `selection_audit.json` and other shared artifacts.
- **Memory**: Atomic runs are memory-intensive; implement a simple memory-aware scheduler if needed (optional for v1).
- **Logging**: Segregate logs by `run_id` to prevent interleaved output in the console.

### 2.3 Integration Path
1. Update `scripts/run_meta_pipeline.py` to support an `--execute-sleeves` flag.
2. If the flag is set and `run_id` is missing in the manifest, the script will trigger `make flow-production` for that profile.
3. Use a pool to manage these shell calls.

## 3. Implementation Plan
1. **Task 223.1**: Implement `scripts/parallel_orchestrator.py` as a reusable utility.
2. **Task 223.2**: Integrate into `run_meta_pipeline.py`.
3. **Task 223.3**: Verify speedup on `meta_benchmark`.
