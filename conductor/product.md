# Product Guide - TradingView Scraper

## Initial Concept
A Python library designed to scrape various data from TradingView.com, including ideas, indicators, news, and real-time market data.

## Target Users
* **Quantitative Traders & Financial Analysts:** Professionals who require reliable, programmatically accessible data for backtesting, strategy development, and deep market analysis.

## Core Goals
* **Unified Pipeline Orchestration:** Transition from raw data scraping to a high-performance, asynchronous quantitative pipeline that adapts to market volatility and risk regimes.
* **Reliability & Performance:** Provide a high-performance and robust interface for accessing TradingView data programmatically, ensuring data integrity and timely delivery.

## Key Features
* **Asynchronous Quantitative Pipeline (V1):** A unified orchestrator that parallelizes discovery, alpha generation, and risk optimization, reducing discovery latency by >60%.
* **Robust Risk Management:** Integrated market regime detection (QUIET/NORMAL/CRISIS) and covariance shrinkage (Ledoit-Wolf) to ensure numerically stable and adaptive portfolio construction.
* **Taleb-Inspired Antifragile Allocation:** Support for Barbell optimization that shifts risk budgets toward a safe core during market stress while maintaining exposure to convex tail-gain aggressors.
* **Real-time Async Streaming:** Modern, `asyncio`-based WebSocket architecture for non-blocking, multi-asset data streaming. Features automated heartbeat handling and state recovery for high-uptime real-time monitoring.
* **Architecture Parity:** 100% logic and data format parity between synchronous and asynchronous modules. Shared serialization ensures that data structures remain consistent regardless of the execution model.
* **Comprehensive Data Extraction:** Scrape a wide range of data points including technical indicators, community ideas, and financial news directly from TradingView.
* **High-Quality Universe Selection:** Sophisticated multi-stage pipeline for selecting tradeable universes based on liquidity (Value.Traded), volatility, and market cap.
* **Dual-Layer Guards:** Enforces strict quality control using a "Hybrid Market Cap Guard" (Rank-based Top N and Floor-based $ minimum) to ensure stability and institutional-grade asset selection.
* **Intelligent Asset Aggregation:** Automatically groups duplicate base assets across multiple quotes and instruments (Spot vs. Perps), providing a unique universe with summed liquidity metrics for accurate ranking and arbitrage opportunity discovery.