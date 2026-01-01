# Product Guide - TradingView Scraper

## Initial Concept
A Python library designed to scrape various data from TradingView.com, including ideas, indicators, news, and real-time market data.

## Target Users
* **Quantitative Traders & Financial Analysts:** Professionals who require reliable, programmatically accessible data for backtesting, strategy development, and deep market analysis.

## Core Goals
* **Unified Pipeline Orchestration:** Transition from raw data scraping to a high-performance, asynchronous quantitative pipeline that adapts to market volatility and risk regimes.
* **Reliability & Performance:** Provide a high-performance and robust interface for accessing TradingView data programmatically, ensuring data integrity and timely delivery.
* **Selection Alpha Positive Expectancy:** Ensure that the "Natural Selection" (pruning) process consistently outperforms the raw discovery pool. The pruned universe must demonstrate higher risk-adjusted returns than the broader market, validating the value of the filter.

## Key Features
* **Asynchronous Quantitative Pipeline (V2):** A formalized 14-step orchestrator that parallelizes discovery, alpha generation, and risk optimization. Features stateful resumability and 100% decision auditability.
* **High-Fidelity Implementation Simulation:** Institutional-grade backtesting that models slippage, commissions, and borrow costs via `cvxportfolio`. Includes warm-start support to eliminate first-trade bias and cross-window state persistence.
* **Immutable Decision Ledger:** Chained SHA-256 audit logs (`audit.jsonl`) that provide a cryptographic record of every pipeline intent and outcome, ensuring deterministic data lineage and reproducibility.
* **Advanced Risk Management:** Integrated market regime detection (QUIET/NORMAL/TURBULENT/CRISIS) using DWT Spectral Turbulence and PIT risk auditing to ensure adaptive portfolio construction.
* **Taleb-Inspired Antifragile Allocation:** Support for Barbell optimization that shifts risk budgets toward a safe core during market stress while maintaining exposure to convex tail-gain aggressors. Now with dynamic regime-based aggressor scaling.
* **Isolated Alpha Attribution:** Systematic separation of Selection Alpha (pruning value) from Optimization Alpha (weighting value), enabling granular strategy teardowns.
* **Real-time Async Streaming:** Modern, `asyncio`-based WebSocket architecture for non-blocking, multi-asset data streaming. Features automated heartbeat handling and state recovery for high-uptime real-time monitoring.
* **Architecture Parity:** 100% logic and data format parity between synchronous and asynchronous modules. Shared serialization ensures that data structures remain consistent regardless of the execution model.
* **Comprehensive Data Extraction:** Scrape a wide range of data points including technical indicators, community ideas, and financial news directly from TradingView.
* **High-Quality Universe Selection:** Sophisticated multi-stage pipeline for selecting tradeable universes based on liquidity (Value.Traded), volatility, and market cap.
* **Dual-Layer Guards:** Enforces strict quality control using a "Hybrid Market Cap Guard" (Rank-based Top N and Floor-based $ minimum) to ensure stability and institutional-grade asset selection.
* **Intelligent Asset Aggregation:** Automatically groups duplicate base assets across multiple quotes and instruments (Spot vs. Perps), providing a unique universe with summed liquidity metrics for accurate ranking and arbitrage opportunity discovery.