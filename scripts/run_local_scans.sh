#!/bin/bash
set -e

echo "Starting Universe Trend Scans..."

echo "----------------------------------------"
echo "1. Running Futures Trend Scan..."
uv run python -m tradingview_scraper.futures_universe_selector \
  --config configs/futures_trend_momentum.yaml \
  --export json

echo "----------------------------------------"
echo "2. Running CFD Trend Scan..."
uv run python -m tradingview_scraper.cfd_universe_selector \
  --config configs/cfd_trend_momentum.yaml \
  --export json

echo "----------------------------------------"
echo "3. Running Forex Trend Scan..."
uv run python -m tradingview_scraper.cfd_universe_selector \
  --config configs/forex_trend_momentum.yaml \
  --export json

echo "----------------------------------------"
echo "4. Running US ETF Trend Scan..."
uv run python -m tradingview_scraper.futures_universe_selector \
  --config configs/us_etf_trend_momentum.yaml \
  --export json

echo "----------------------------------------"
echo "5. Running US Stocks Trend Scan..."
uv run python -m tradingview_scraper.futures_universe_selector \
  --config configs/us_stocks_trend_momentum.yaml \
  --export json

echo "----------------------------------------"
echo "All scans completed successfully. Results are in export/"
