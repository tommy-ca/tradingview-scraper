# Idealized V2 Design: Triple-Pipeline Architecture (Pillar-Neutral)

## 1. Vision
Transform the TradingView Scraper platform into a series of orthogonal, composable pipelines that communicate via standardized Pydantic Contexts. This enforces the Single Responsibility Principle and allows for "Plug-and-Play" quant research.

## 2. The Triple-Pipeline Flow

### 2.1 Discovery Pipeline (`DiscoveryContext`)
- **Pillar 0**: Symbol identification and ingestion.
- **Input**: Venue Config (e.g., Binance Spot).
- **Output**: `ReturnsMatrix` and `CandidatePool`.

### 2.2 Selection Pipeline (`SelectionContext`)
- **Pillar 1 (Alpha)**: Rank assets based on feature scores (MPS, Trend, etc.).
- **Pillar 2 (Synthesis)**: Transform returns into alpha-biased streams.
- **Stages**: `FeatureEng` -> `Inference` -> `Partitioning` -> `Synthesis`.

### 2.3 Allocation Pipeline (`AllocationContext`)
- **Pillar 3 (Risk)**: Optimize weights and execute simulation.
- **Stages**: `Optimization` -> `ConstraintHardening` -> `Simulation` -> `Reporting`.

## 3. The Modular `BacktestEngine` (V2)

The engine moves from being the "Doer" to the "Coordinator":

```python
class BacktestEngine:
    def run_tournament(self):
        orchestrator = TournamentOrchestrator(self.settings)
        
        for window in orchestrator.windows():
            # 1. Selection
            selection_pipe = SelectionPipeline(window)
            sel_context = selection_pipe.run()
            
            # 2. Allocation
            allocation_pipe = AllocationPipeline(sel_context)
            all_context = allocation_pipe.run()
            
            # 3. State Management
            self.state_manager.update(all_context.final_holdings)
```

## 4. Key Architectural Components

### 4.1 `TelemetryProvider`
- A unified mixin or service used by every `Stage`.
- Decouples quant logic from MLflow/Audit hooks.
- Interface: `telemetry.log_feature_importance(df)`, `telemetry.log_solver_diag(metrics)`.

### 4.2 `NumericalWorkspace`
- JIT pre-allocated memory pool for vectorized operations.
- Shared across all pipeline stages to minimize GC pressure.

### 4.3 `DataContract` (Pandera V2)
- Explicit schemas for every handoff point.
- `ReturnsSchema` (Input) -> `AlphaSignalSchema` (Intermediate) -> `PortfolioWeightsSchema` (Output).

## 5. Benefits
- **Testability**: Every stage is a pure function of `Context`.
- **Parallelism**: Stages can be easily dispatched to Ray workers without state leakage.
- **Auditability**: The `Context` snapshots itself at every stage, creating a "Full History" of the decision logic.
