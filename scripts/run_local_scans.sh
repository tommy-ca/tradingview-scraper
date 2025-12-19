#!/bin/bash
set -e

echo "Starting Universe Trend Scans..."

echo "----------------------------------------"
echo "1. Running Futures Trend Scan (Long)..."
uv run python -m tradingview_scraper.futures_universe_selector \
  --config configs/futures_trend_momentum.yaml \
  --export json

echo "1b. Running Futures Trend Scan (Short)..."
uv run python -m tradingview_scraper.futures_universe_selector \
  --config configs/futures_trend_momentum_short.yaml \
  --export json

echo "1c. Running Futures Metals Trend Scan (Long)..."
uv run python -m tradingview_scraper.futures_universe_selector \
  --config configs/futures_metals_trend_momentum.yaml \
  --export json

echo "1d. Running Futures Metals Trend Scan (Short)..."
uv run python -m tradingview_scraper.futures_universe_selector \
  --config configs/futures_metals_trend_momentum_short.yaml \
  --export json

echo "----------------------------------------"
echo "2. Running CFD Trend Scan (Long)..."
uv run python -m tradingview_scraper.cfd_universe_selector \
  --config configs/cfd_trend_momentum.yaml \
  --export json

echo "2b. Running CFD Trend Scan (Short)..."
uv run python -m tradingview_scraper.cfd_universe_selector \
  --config configs/cfd_trend_momentum_short.yaml \
  --export json

echo "----------------------------------------"
echo "3. Running Forex Trend Scan (Long)..."
uv run python -m tradingview_scraper.cfd_universe_selector \
  --config configs/forex_trend_momentum.yaml \
  --export json

echo "3b. Running Forex Trend Scan (Short)..."
uv run python -m tradingview_scraper.cfd_universe_selector \
  --config configs/forex_trend_momentum_short.yaml \
  --export json

echo "----------------------------------------"
echo "4. Running US ETF Trend Scan (Long)..."
uv run python -m tradingview_scraper.futures_universe_selector \
  --config configs/us_etf_trend_momentum.yaml \
  --export json

echo "4b. Running US ETF Trend Scan (Short)..."
uv run python -m tradingview_scraper.futures_universe_selector \
  --config configs/us_etf_trend_momentum_short.yaml \
  --export json

echo "----------------------------------------"
echo "5. Running US Stocks Trend Scan (Long)..."
uv run python -m tradingview_scraper.futures_universe_selector \
  --config configs/us_stocks_trend_momentum.yaml \
  --export json

echo "5b. Running US Stocks Trend Scan (Short)..."
uv run python -m tradingview_scraper.futures_universe_selector \
  --config configs/us_stocks_trend_momentum_short.yaml \
  --export json

echo "----------------------------------------"
echo "6. Running Crypto Spot Trend Scan (Long)..."
uv run python -m tradingview_scraper.futures_universe_selector \
  --config configs/crypto_cex_trend_momentum_spot_daily_long.yaml \
  --export json

echo "6b. Running Crypto Spot Trend Scan (Short)..."
uv run python -m tradingview_scraper.futures_universe_selector \
  --config configs/crypto_cex_trend_momentum_spot_daily_short.yaml \
  --export json

echo "----------------------------------------"
echo "7. Running Crypto Perp Trend Scan (Long)..."
uv run python -m tradingview_scraper.futures_universe_selector \
  --config configs/crypto_cex_trend_momentum_perp_daily_long.yaml \
  --export json

echo "7b. Running Crypto Perp Trend Scan (Short)..."
uv run python -m tradingview_scraper.futures_universe_selector \
  --config configs/crypto_cex_trend_momentum_perp_daily_short.yaml \
  --export json

echo "----------------------------------------"
echo "All scans completed successfully. Results are in export/"
