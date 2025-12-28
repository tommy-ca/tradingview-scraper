#!/bin/bash
set -e

echo "Starting Crypto Exchange Trend Scans..."

# Binance
echo "----------------------------------------"
echo "1. Binance Spot Long..."
uv run -m tradingview_scraper.futures_universe_selector \
  --config configs/crypto_cex_trend_binance_spot_daily_long.yaml \
  --export json

echo "1b. Binance Spot Short..."
uv run -m tradingview_scraper.futures_universe_selector \
  --config configs/crypto_cex_trend_binance_spot_daily_short.yaml \
  --export json

echo "1c. Binance Perp Long..."
uv run -m tradingview_scraper.futures_universe_selector \
  --config configs/crypto_cex_trend_binance_perp_daily_long.yaml \
  --export json

echo "1d. Binance Perp Short..."
uv run -m tradingview_scraper.futures_universe_selector \
  --config configs/crypto_cex_trend_binance_perp_daily_short.yaml \
  --export json

# OKX
echo "----------------------------------------"
echo "2. OKX Spot Long..."
uv run -m tradingview_scraper.futures_universe_selector \
  --config configs/crypto_cex_trend_okx_spot_daily_long.yaml \
  --export json

echo "2b. OKX Spot Short..."
uv run -m tradingview_scraper.futures_universe_selector \
  --config configs/crypto_cex_trend_okx_spot_daily_short.yaml \
  --export json

echo "2c. OKX Perp Long..."
uv run -m tradingview_scraper.futures_universe_selector \
  --config configs/crypto_cex_trend_okx_perp_daily_long.yaml \
  --export json

echo "2d. OKX Perp Short..."
uv run -m tradingview_scraper.futures_universe_selector \
  --config configs/crypto_cex_trend_okx_perp_daily_short.yaml \
  --export json

# Bybit
echo "----------------------------------------"
echo "3. Bybit Spot Long..."
uv run -m tradingview_scraper.futures_universe_selector \
  --config configs/crypto_cex_trend_bybit_spot_daily_long.yaml \
  --export json

echo "3b. Bybit Spot Short..."
uv run -m tradingview_scraper.futures_universe_selector \
  --config configs/crypto_cex_trend_bybit_spot_daily_short.yaml \
  --export json

echo "3c. Bybit Perp Long..."
uv run -m tradingview_scraper.futures_universe_selector \
  --config configs/crypto_cex_trend_bybit_perp_daily_long.yaml \
  --export json

echo "3d. Bybit Perp Short..."
uv run -m tradingview_scraper.futures_universe_selector \
  --config configs/crypto_cex_trend_bybit_perp_daily_short.yaml \
  --export json

# Bitget
echo "----------------------------------------"
echo "4. Bitget Spot Long..."
uv run -m tradingview_scraper.futures_universe_selector \
  --config configs/crypto_cex_trend_bitget_spot_daily_long.yaml \
  --export json

echo "4b. Bitget Spot Short..."
uv run -m tradingview_scraper.futures_universe_selector \
  --config configs/crypto_cex_trend_bitget_spot_daily_short.yaml \
  --export json

echo "4c. Bitget Perp Long..."
uv run -m tradingview_scraper.futures_universe_selector \
  --config configs/crypto_cex_trend_bitget_perp_daily_long.yaml \
  --export json

echo "4d. Bitget Perp Short..."
uv run -m tradingview_scraper.futures_universe_selector \
  --config configs/crypto_cex_trend_bitget_perp_daily_short.yaml \
  --export json

echo "----------------------------------------"
echo "All crypto scans completed successfully. Results are in export/"
