# TradingView Scraper
[![Python 3.8](https://img.shields.io/badge/python-3.8-blue.svg)](https://www.python.org/downloads/release/python-380/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![MIT License](https://img.shields.io/github/license/mnwato/tradingview-scraper.svg?color=brightgreen)](https://opensource.org/licenses/MIT)


This is a Python library for scraping ideas and indicators from [TradingView.com](https://www.tradingview.com). The goal is to develop this package to scrape anything on [TradingView.com](https://www.tradingview.com) with real-time responses.  
**Thanks to contributors!**


## To-Do List
- Export
  - [x] Export as a `CSV` file
  - [x] Export as `JSON`
- Scrape Symbol Subpages:
  - [x] [Ideas](https://www.tradingview.com/symbols/BTCUSD/ideas/)
  - [x] [Indicators](https://www.tradingview.com/symbols/BTCUSD/technicals/)
  - [x] [Overview](https://www.tradingview.com/symbols/BTCUSD/)
  - [x] [News](https://www.tradingview.com/symbols/BTCUSD/news/)
  - [x] [Earning-calendar](https://in.tradingview.com/earnings-calendar/)
  - [x] [Minds](https://www.tradingview.com/symbols/BTCUSD/minds/)
  - [x] [Technical](https://www.tradingview.com/symbols/BTCUSD/technicals/)
  - [x] [Symbol-Market](https://www.tradingview.com/symbols/BTCUSD/markets/)
  - [x] [Markets](https://www.tradingview.com/markets)
  - [x] [Markets-Quotes](https://www.tradingview.com/markets/stocks-usa/market-movers-penny-stocks/)
  - [x] [Screener](https://www.tradingview.com/screener/)
  - [x] [Fundamental-Graphs](https://www.tradingview.com/fundamental-graphs/?selected-metric=STD%3BFund_total_revenue_fq&symbols=NASDAQ%3AAAPL%2CNASDAQ%3AGOOGL&metrics=STD%3BFund_total_revenue_fq/)
  - [x] Get 'OHLC', 'Indicators' using TradingView WebSocket
  - [x] Export historical OHLC candle and Indicator values
  
  Additional suggestions welcome!

### To be aware of the latest changes, go to the [end of this page](https://github.com/mnwato/tradingview-scraper#changes).

## Features

- **Idea page Scraping**
  - Title
  - Paragraph
  - Preview Image
  - Author
  - Comments Count
  - Boosts Count
  - Publication Datetime
  - Is Updated
  - Idea Strategy

- **News page Scraping**
  - Breadcrumbs
  - Title
  - Published datetime
  - Related symbols
  - Body
  - Tags

- **Webpage Scraping Options**
  - Scrape All Pages
  - Scrape a Specific Range of Pages

- **Indicator Extraction**
  - Extract values for indicators like `RSI`, `Stoch.K`, etc. 
  - [Full list of indicators](https://github.com/mnwato/tradingview-scraper/blob/dev/tradingview_scraper/indicators.txt)

- **Real-Time data Extraction**
  - OHLCV
  - Watchlist
  - Indicators

- **Market Movers Scraping**
  - Gainers
  - Losers
  - Most Active
  - Penny Stocks
  - Pre-market Gainers/Losers
  - After-hours Gainers/Losers
  - Multiple markets support (USA, UK, India, Australia, Canada, Crypto, Forex, Bonds, Futures)

- **Screener**
  - Custom filters (price, volume, market cap, technical indicators, etc.)
  - Multiple filter operations (greater, less, equal, in_range, crosses, etc.)
  - Custom column selection
  - Sorting by any field
  - Support for 18 markets (America, Canada, Germany, India, UK, Crypto, Forex, CFD, Futures, Bonds, etc.)

- **Symbol Markets**
  - Find all exchanges/markets where a symbol is traded
  - Global, regional, and market-specific scanners
  - Support for stocks, crypto, forex, CFD markets
  - Detailed market information (price, volume, exchange, currency, etc.)

- **Markets Overview**
  - Top stocks by market cap, volume, change, price, volatility
  - Multiple market support (America, Australia, Canada, Germany, India, UK, Crypto, Forex, Global)
  - Customizable sorting and column selection
  - Real-time market data

- **Symbol Overview**
  - Comprehensive symbol data (profile, statistics, financials, performance, technicals)
  - Support for stocks, crypto, forex, and other instruments
  - Categorized data fields (basic, price, market, valuation, dividends, financials, performance, volatility, technical)
  - Helper methods for specific data categories (profile, statistics, financials, performance, technicals)

- **Minds Community Discussions**
  - Community-generated discussions, questions, and trading ideas
  - Multiple sort options (recent, popular, trending)
  - Pagination support for retrieving all discussions
  - User information (username, profile, likes, comments)
  - Symbol mentions and engagement metrics

- **Fundamental Financial Data**
  - Comprehensive fundamental metrics for financial analysis
  - Income statement data (revenue, profit, earnings, EBITDA)
  - Balance sheet data (assets, debt, equity, cash)
  - Cash flow statement data (operating, investing, financing activities)
  - Profitability ratios (ROE, ROA, ROI)
  - Liquidity ratios (current ratio, quick ratio)
  - Leverage ratios (debt-to-equity, debt-to-assets)
  - Margin metrics (gross, operating, net, EBITDA margins)
  - Valuation metrics (market cap, enterprise value, P/E, P/B, P/S)
  - Dividend information (yield, per share, payout ratio)
  - Multi-symbol comparison support

- **Export Formats**
  - CSV
  - JSON

- **Output Format**
  - Returns data in JSON format

Here’s a revised version of the Installation section that enhances clarity and encourages user engagement:


## Installation

To get started with the TradingView Scraper library, follow these simple steps:

1. **Open your terminal**: Launch your preferred command line interface.

2. **Install with uv** (recommended):
   ```sh
   uv venv
   source .venv/bin/activate
   uv pip install tradingview-scraper
   ```

3. **Upgrade if necessary**:
   ```sh
   uv pip install --upgrade tradingview-scraper
   ```


## Development with uv

For consistent and reproducible development environments, this project uses [uv](https://github.com/astral-sh/uv).

1. **Install uv**:
   ```sh
   curl -LsSf https://astral-sh.uv.io/install.sh | sh
   ```

2. **Sync dependencies**:
   ```sh
   uv sync --extra dev
   ```

3. **Run tests**:
   ```sh
   uv run pytest
   ```

4. **Run scanners**:
   ```sh
   uv run -m tradingview_scraper.futures_universe_selector --config configs/futures_trend_momentum.yaml
   ```

All CI/CD workflows and local shell scripts (`scripts/*.sh`) are optimized to use `uv` for speed and consistency.

## Available Resolutions

The library supports both standard and discovery resolutions via the `Streamer` and `DataLoader` classes:

*   **Standard:** `1m`, `5m`, `15m`, `30m`, `1h`, `4h`, `1d`, `1w`, `1M`
*   **Discovery:** `3m`, `45m`, `2h`, `3h`
*   **Notes:** Second-level resolutions (`1s`, `5s`) are not supported on the free tier. Intraday lookback is capped at ~8,500 candles.

## Research & Development

The following research reports outline advanced capabilities and feasibility studies for institutional trading:

- [Binance Multi-Quote Arbitrage Exploration](docs/research/arbitrage_research_20251220.md) - Analysis of spreads between USDT, USDC, and FDUSD pairs.
- [Real-Time Streamer & Data Lakehouse Feasibility](docs/research/streamer_research_20251220.md) - Technical deep-dive into WebSocket schemas and ingestion architecture.
- [Historical OHLCV & Technical Indicator Precision](docs/research/historical_technicals_20251220.md) - Research on 1m/1h data depth and multi-indicator retrieval.
- [Multi-Timeframe Technical Filtering](docs/research/mtf_technical_filtering_20251220.md) - Strategy for refining trend candidates using 15m/1h/1d indicator alignment.
- [Alternative Technical Indicators via Scanner API](docs/research/alternative_technicals_20251220.md) - Validation of 30+ pre-calculated indicators for deep structural analysis.
- [Historical Data Loader Pattern](docs/research/historical_loader_20251220.md) - Interface for date-range based data acquisition for backtesting.
- [Multi-Market Data Loading Research](docs/research/dataloader_multi_market_20251220.md) - Validation across Crypto, Forex, Stocks, Indices, and Commodities.
- [Deep History & Genesis Reach Feasibility](docs/research/deep_history_feasibility_20251220.md) - Analysis of maximum lookback limits for building crypto data lakehouses.
- [Persistent Data Loading & Lakehouse Ingestion](docs/research/lakehouse_ingestor_20251220.md) - Implementation of a stateful loader for deep historical accumulation.
- [Lakehouse Data Quality & Gap Management](docs/research/lakehouse_gap_management_20251220.md) - Automated detection and repair of missing historical data.
- [Data Resilience & Stabilization (v2)](docs/specs/data_resilience_v2.md) - Specs for WebSocket guardrails, Genesis detection, and mixed-universe alignment.
- [Portfolio Artifact Validation](scripts/validate_portfolio_artifacts.py) - Categorized health dashboard for mixed asset universes.
- [Multi-Engine Optimization Benchmarks](docs/specs/multi_engine_optimization_benchmarks.md) - Framework for comparing skfolio, Riskfolio-Lib, PyPortfolioOpt, and CVXPortfolio.
- [Optimization Learnings & Comparison](docs/research/optimization_learnings_20251224.md) - Analysis of MPT, Robust, and Antifragile Barbell models.


- [Historical Candle Resolution & Depth Matrix](docs/research/resolution_matrix_20251220.md) - Mapping of all verified TradingView timeframes and their limits.
- [Stress & Performance Load Testing](docs/research/performance_load_tests_20251220.md) - Benchmarks for storage latency and concurrent ingestion throughput.
- [Data Schema Normalization & Gap Analysis](docs/research/schema_gap_analysis_20251220.md) - Comparison with Tardis.dev standards and proposal for a normalized data model.

## Examples

### 1. Fast Running (Default Parameters)
To quickly scrape ideas using default settings, use the following code:
```python
from tradingview_scraper.symbols.ideas import Ideas

# Initialize the Ideas scraper with default parameters
ideas_scraper = Ideas()  # Default: export_result=False, export_type='json'
ideas = ideas_scraper.scrape()  # Default symbol: 'BTCUSD'
print("Ideas:", ideas)
```
**Default Parameters:**
- `export_result`: `False` (no file will be saved)
- `export_type`: `'json'` (output format)

### 2. Getting Ideas for a Specific Symbol, Export Type, and Pages
To scrape ideas for a specific symbol and export them as a CSV file, you can specify the parameters:
```python
from tradingview_scraper.symbols.ideas import Ideas

# Initialize the Ideas scraper with custom parameters
ideas_scraper = Ideas(
  export_result=True,  # Set to True to save the results
  export_type='csv'    # Specify the export type (json or csv)
)

# Scrape ideas for the ETHUSD symbol, from page 1 to page 2
ideas = ideas_scraper.scrape(
  symbol="ETHUSD",
  startPage=1,
  endPage=2,
  sort="popular"  # Could be 'popular' or 'recent'
)
print("Ideas:", ideas)
```

#### Using Cookie for Captcha Bypass
To avoid captcha challenges, set your TradingView cookie as an environment variable:

1. Open https://www.tradingview.com/symbols/BTCUSD/ideas/ in your browser
2. Open Developer Tools (F12) and go to Network tab
3. Verify the captcha if prompted
4. Refresh the page and find the GET request at the top of the list with URL `https://www.tradingview.com/symbols/BTCUSD/ideas/`
5. Copy the cookie value and add it to your `.env` file:
   ```
   TRADINGVIEW_COOKIE=your_cookie_here
   ```

```python
from tradingview_scraper.symbols.ideas import Ideas

ideas_scraper = Ideas()
ideas = ideas_scraper.scrape(symbol="BTCUSD")
```

**Output Format:**
The output will always be a list of Python dictionaries, structured as follows:
```json
[
  {
    "title": "Bitcoin Analysis: Bullish Momentum Building",
    "description": "Technical analysis showing strong bullish signals...",
    "preview_image": ["https://s3.tradingview.com/logo.png"],
    "chart_url": "https://www.tradingview.com/chart/BTCUSD/...",
    "comments_count": 25,
    "views_count": 1250,
    "author": "CryptoAnalyst",
    "likes_count": 45,
    "timestamp": 1672531200
  }
]
```

- When `export_result=True`, the default `export_type` is `'json'`, and a JSON file will be saved in the `/export` directory. To save as CSV, set `export_type='csv'`.

### 3. Getting Indicators Status
To scrape the status of specific indicators, use the following code:
```python
from tradingview_scraper.symbols.technicals import Indicators

# Initialize the Indicators scraper with export options
indicators_scraper = Indicators(export_result=True, export_type='json')

# Scrape indicators for the BTCUSD symbol from the BINANCE exchange
indicators = indicators_scraper.scrape(
    exchange="BINANCE",
    symbol="BTCUSD",
    timeframe="1d",
    indicators=["RSI", "Stoch.K"]
)
print("Indicators:", indicators)
```

**Output:**
```json
{
  "status": "success",
  "data": {
    "RSI": "46.34926112",
    "Stoch.K": "40.40173723"
  }
}
```

### 4. Getting All Indicators
If you want to retrieve all available indicators for a symbol, set `allIndicators=True`:
```python
from tradingview_scraper.symbols.technicals import Indicators

# Scrape all indicators for the BTCUSD symbol
indicators_scraper = Indicators(export_result=True, export_type='json')
indicators = indicators_scraper.scrape(
    symbol="BTCUSD",
    timeframe="4h",
    allIndicators=True
)
print("All Indicators:", indicators)
```

### 5. Getting News Headlines/Content

#### Quick start: headlines
```python
from tradingview_scraper.symbols.news import NewsScraper

scraper = NewsScraper(export_result=True, export_type='json')
headlines = scraper.scrape_headlines(
    symbol='BTCUSD',
    exchange='BINANCE',
    provider='cointelegraph',  # optional filter
    area='americas',           # optional filter (see data/areas.json)
    sort='latest',             # latest | oldest | most_urgent | least_urgent
)
print(headlines[:2])  # returns a list, not wrapped in a dict
```

#### Fetch story body
```python
story_path = headlines[0].get('storyPath') or headlines[0].get('link', '').replace('https://tradingview.com', '')
article = scraper.scrape_news_content(story_path)
print(article['title'])
```

#### Workflows
- Polling: schedule `scrape_headlines` by symbol+exchange (required) and dedupe by `id`/`storyPath`.
- Drill-down: fetch full bodies only for new headlines; store `related_symbols` for routing.
- Export: enable `export_result` to write JSON/CSV into `export/` (filenames prefixed with `news_*`).
- Filtering knobs: `provider`, `area`, `section` (`all`/`esg`), `language` (see `data/languages.json`).
- Caveats: no WebSocket/streaming; this is HTTP polling. Inputs require both `symbol` and `exchange`.

#### CLI: poll headlines (and bodies)
```bash
uv run -m tradingview_scraper.symbols.news \
  --exchange BINANCE \
  --symbols BTCUSD,ETHUSD \
  --provider cointelegraph \
  --sort latest \
  --max-headlines 10 \
  --fetch-content \
  --content-limit 2 \
  --export json
```
- Returns JSON to stdout and (if `--export` is set) writes files to `export/`.

#### Output (news headline):
```json
[
  {
    "id": "tag:reuters.com,2024:newsml_L1N3KM09S:0",
    "title": "Goldman Sachs sees biggest boost to US economy from Harris win",
    "provider": "reuters",
    "sourceLogoId": "reuters",
    "published": 1725443676,
    "source": "Reuters",
    "urgency": 2,
    "permission": "preview",
    "relatedSymbols": [
      {"symbol": "BITMEX:XBTETH.P"},
      {"symbol": "ICEUS:DXY"}
    ],
    "storyPath": "/news/reuters.com,2024:newsml_L1N3KM09S:0-goldman-sachs-sees-biggest-boost-to-us-economy-from-harris-win/"
  }
]
```
#### Output (news content):

```json
{
  "status": "success",
  "data": {
    "breadcrumbs": "News > U.Today > Bitcoin ETFs Record Enormous Outflows",
    "title": "Bitcoin ETFs Record Enormous Outflows",
    "published_datetime": "Wed, 04 Sep 2024 07:55:38 GMT",
    "related_symbols": [
      {
        "name": "BTCUSDT",
        "logo": "https://s3-symbol-logo.tradingview.com/crypto/XTVCUSDT.svg"
      }
    ],
    "body": ["<List of text page content>"],
    "tags": ["Crypto", "U.Today"]
  }
}
```

### 6. Streaming and Historical Data (WebSocket)
- Two paths: `RealTimeData` for simple real-time quotes/1m series; `Streamer` for bounded historical candles plus optional indicators (and an option to keep streaming).
- Timeframes supported in the chart series: `1m`, `5m`, `15m`, `30m`, `1h`, `2h`, `4h`, `1d`, `1w`, `1M`.
- Exports go to the `export/` directory (JSON/CSV) with filenames like `ohlc_<symbol>_<timestamp>.json`.

#### Quick start: historical export + optional indicators
```python
from tradingview_scraper.symbols.stream import Streamer

streamer = Streamer(
    export_result=True,            # return dict and write files
    export_type="json",           # or "csv"
    websocket_jwt_token="<TV JWT>", # required for indicators
    max_retries=5,                # optional: max reconnection attempts (default: 5)
    initial_delay=1.0,            # optional: initial delay in seconds (default: 1.0)
    max_delay=60.0,               # optional: maximum delay in seconds (default: 60.0)
    backoff_factor=2.0            # optional: exponential backoff factor (default: 2.0)
)

result = streamer.stream(
    exchange="BINANCE",
    symbol="BTCUSDT",
    timeframe="4h",
    numb_price_candles=200,
    indicators=[("STD;RSI", "31.0")],  # optional list of (id, version)
)
print(result["ohlc"][:2])
```
- Returns `{"ohlc": [...], "indicator": {...}}` once it sees `numb_price_candles` (and all requested indicators). Use this for backfill slices; loop multiple calls to walk backward in time.
- **Robustness:** `Streamer` now includes an automatic reconnection mechanism with exponential backoff. It will automatically re-subscribe to your symbols and indicators after a connection loss.

#### Quick start: live stream with warm start
```python
from tradingview_scraper.symbols.stream import Streamer

# Grab a warm-start history, then continue streaming packets
streamer = Streamer(export_result=True)
backfill = streamer.stream("BINANCE", "BTCUSDT", timeframe="1h", numb_price_candles=200)

streamer_live = Streamer(export_result=False)
gen = streamer_live.stream("BINANCE", "BTCUSDT", timeframe="1h", numb_price_candles=1)
for pkt in gen:
    print(pkt)  # handle incoming packets; merge with backfill on timestamp
```

#### Simple real-time quotes / OHLCV (no export)
```python
from tradingview_scraper.symbols.stream import RealTimeData
rt = RealTimeData()
data_generator = rt.get_ohlcv(exchange_symbol="BINANCE:BTCUSDT")
for packet in data_generator:
    print(packet)
```

#### Watchlist snapshot (quote fields)
```python
from tradingview_scraper.symbols.stream import RealTimeData
rt = RealTimeData()
exchange_symbol = ["BINANCE:BTCUSDT", "BINANCE:ETHUSDT", "FXOPEN:XAUUSD"]
data_generator = rt.get_latest_trade_info(exchange_symbol=exchange_symbol)
for packet in data_generator:
    print(packet)
```

#### Notes and caveats
- Indicator output schema is indicator-dependent; map the numbered fields (`0`, `1`, …) per indicator manually.
- No built-in support for open interest/funding fields; only TA indicators and OHLC(+volume) are handled.
- Add your own retry/backoff around `Streamer.stream` for robustness; current code stops on socket close.

### 7. Historical Data Loading (Backtesting)
The `DataLoader` class provides a standardized interface for fetching specific date ranges, while `PersistentDataLoader` adds a local Parquet-based caching layer (Data Lakehouse) to overcome API limits.

#### Range-based Loading (DataLoader)
```python
from datetime import datetime, timedelta
from tradingview_scraper.symbols.stream.loader import DataLoader

loader = DataLoader()
start_dt = datetime.now() - timedelta(days=3)
end_dt = datetime.now()

# Supports standard (1m, 1h, 1d) and discovery (3m, 45m, 3h) resolutions
data = loader.load("BINANCE:BTCUSDT", start=start_dt, end=end_dt, interval="15m")
print(f"Loaded {len(data)} candles.")
```

#### Stateful Ingestion (PersistentDataLoader)
```python
from tradingview_scraper.symbols.stream.persistent_loader import PersistentDataLoader

# Automatically manages a local Parquet lakehouse in data/lakehouse
pd_loader = PersistentDataLoader()

# Sync the last 8500 candles (API limit) into local storage
pd_loader.sync("BINANCE:BTCUSDT", interval="1m")

# Load from local storage, falling back to API if range is missing
df = pd_loader.load("BINANCE:BTCUSDT", start="2025-12-15", end="2025-12-20", interval="1m")
print(df.head())

# Self-heal missing data segments
pd_loader.repair("BINANCE:BTCUSDT", interval="1m")
```

### 8. Getting Calendar events


#### Scraping Earnings events
```python
from tradingview_scraper.symbols.cal import CalendarScraper

calendar_scraper = CalendarScraper()

# Scrape earnings from all markets.
res = calendar_scraper.scrape_earnings(
  values=["logoid", "name", "earnings_per_share_fq"]
)


# Scrape upcoming week earnings from the american market
from datetime import datetime, timedelta

timestamp_now = datetime.now().timestamp()
timestamp_in_7_days = (datetime.now() + timedelta(days=7)).timestamp()

res = calendar_scraper.scrape_earnings(
  timestamp_now,
  timestamp_in_7_days,
  ["america"],
  values=["logoid", "name", "earnings_per_share_fq"]
  )
```

#### Scraping Dividend events
```python
from tradingview_scraper.symbols.cal import CalendarScraper

calendar_scraper = CalendarScraper()

# Scrape dividends from all markets.
res = calendar_scraper.scrape_dividends(
  values=["logoid", "name", "dividends_yield"]
)


# Scrape upcoming week dividends from the american market
from datetime import datetime, timedelta

timestamp_now = datetime.now().timestamp()
timestamp_in_7_days = (datetime.now() + timedelta(days=7)).timestamp()

res = calendar_scraper.scrape_dividends(
  timestamp_now,
  timestamp_in_7_days,
  ["america"],
  values=["logoid", "name", "dividends_yield"]
  )
```

### 8. Getting Market Movers Data

The `MarketMovers` class allows you to scrape market movers data such as gainers, losers, most active stocks, penny stocks, and pre-market/after-hours movers.

#### Scraping Top Gainers
```python
from tradingview_scraper.symbols.market_movers import MarketMovers

# Create an instance of MarketMovers
market_movers = MarketMovers(export_result=True, export_type='json')

# Get top gainers from US stock market
gainers = market_movers.scrape(
    market='stocks-usa',
    category='gainers',
    limit=20
)

print("Top Gainers:", gainers['data'])
```

#### Scraping Penny Stocks
```python
from tradingview_scraper.symbols.market_movers import MarketMovers

market_movers = MarketMovers()

# Get penny stocks (stocks trading below $5)
penny_stocks = market_movers.scrape(
    market='stocks-usa',
    category='penny-stocks',
    limit=50
)

print("Penny Stocks:", penny_stocks['data'])
```

#### Scraping Pre-Market Gainers
```python
from tradingview_scraper.symbols.market_movers import MarketMovers

market_movers = MarketMovers()

# Get pre-market gainers
premarket_gainers = market_movers.scrape(
    market='stocks-usa',
    category='pre-market-gainers',
    limit=30
)

print("Pre-Market Gainers:", premarket_gainers['data'])
```

#### Scraping with Custom Fields
```python
from tradingview_scraper.symbols.market_movers import MarketMovers

market_movers = MarketMovers()

# Specify only the fields you need
custom_fields = ['name', 'close', 'change', 'volume', 'market_cap_basic']

losers = market_movers.scrape(
    market='stocks-usa',
    category='losers',
    fields=custom_fields,
    limit=10
)

print("Top Losers:", losers['data'])
```

#### Supported Markets
- `stocks-usa`: US Stock Market
- `stocks-uk`: UK Stock Market
- `stocks-india`: Indian Stock Market
- `stocks-australia`: Australian Stock Market
- `stocks-canada`: Canadian Stock Market
- `crypto`: Cryptocurrency Market
- `forex`: Forex Market
- `bonds`: Bonds Market
- `futures`: Futures Market

#### Supported Categories
- `gainers`: Top gaining stocks
- `losers`: Top losing stocks
- `most-active`: Most actively traded stocks
- `penny-stocks`: Stocks trading below $5
- `pre-market-gainers`: Pre-market gainers
- `pre-market-losers`: Pre-market losers
- `after-hours-gainers`: After-hours gainers
- `after-hours-losers`: After-hours losers

#### Output Example:
```json
{
  "status": "success",
  "data": [
    {
      "symbol": "NASDAQ:AAPL",
      "name": "Apple Inc.",
      "close": 150.25,
      "change": 2.5,
      "change_abs": 3.75,
      "volume": 50000000,
      "market_cap_basic": 2500000000000,
      "price_earnings_ttm": 25.5,
      "earnings_per_share_basic_ttm": 6.0,
      "logoid": "apple-logo-id",
      "description": "Technology company"
    }
  ],
  "total": 1
}
```

## 9. Using the Screener

The Screener allows you to filter and screen financial instruments based on custom criteria across multiple markets.

#### Basic Screening
```python
from tradingview_scraper.symbols.screener import Screener

screener = Screener()

# Screen US stocks with default settings
results = screener.screen(market='america', limit=50)
print("Results:", results['data'])
```

#### Screening with Filters
```python
from tradingview_scraper.symbols.screener import Screener

screener = Screener()

# Screen stocks with price > $100 and volume > 1M
filters = [
    {'left': 'close', 'operation': 'greater', 'right': 100},
    {'left': 'volume', 'operation': 'greater', 'right': 1000000}
]

results = screener.screen(
    market='america',
    filters=filters,
    sort_by='volume',
    sort_order='desc',
    limit=20
)

print("Filtered Results:", results['data'])
```

#### Screening Crypto by Market Cap
```python
from tradingview_scraper.symbols.screener import Screener

screener = Screener()

# Screen crypto with market cap > $1B
crypto_filters = [
    {'left': 'market_cap_calc', 'operation': 'greater', 'right': 1000000000}
]

crypto_results = screener.screen(
    market='crypto',
    filters=crypto_filters,
    columns=['name', 'close', 'market_cap_calc', 'change'],
    limit=50
)

print("Top Crypto by Market Cap:", crypto_results['data'])
```

#### Price Range Filtering
```python
from tradingview_scraper.symbols.screener import Screener

screener = Screener()

# Screen stocks in price range $50-$200
range_filters = [
    {'left': 'close', 'operation': 'in_range', 'right': [50, 200]}
]

range_results = screener.screen(
    market='america',
    filters=range_filters,
    limit=30
)

print("Stocks in Range:", range_results['data'])
```

#### Supported Markets
- `america`: US Stock Market
- `australia`: Australian Stock Market
- `canada`: Canadian Stock Market
- `germany`: German Stock Market
- `india`: Indian Stock Market
- `israel`: Israeli Stock Market
- `italy`: Italian Stock Market
- `luxembourg`: Luxembourg Stock Market
- `mexico`: Mexican Stock Market
- `spain`: Spanish Stock Market
- `turkey`: Turkish Stock Market
- `uk`: UK Stock Market
- `crypto`: Cryptocurrency Market
- `forex`: Forex Market
- `cfd`: CFD Market
- `futures`: Futures Market
- `bonds`: Bonds Market
- `global`: Global Market

#### Supported Filter Operations
- `greater`: Greater than
- `less`: Less than
- `egreater`: Equal or greater than
- `eless`: Equal or less than
- `equal`: Equal to
- `nequal`: Not equal to
- `in_range`: Within range [min, max]
- `not_in_range`: Outside range
- `above`: Above (for crosses)
- `below`: Below (for crosses)
- `crosses`: Crosses
- `crosses_above`: Crosses above
- `crosses_below`: Crosses below
- `has`: Has (for categorical fields)
- `has_none_of`: Has none of

#### Output Example:
```json
{
  "status": "success",
  "data": [
    {
      "symbol": "NASDAQ:AAPL",
      "name": "Apple Inc.",
      "close": 150.25,
      "change": 2.5,
      "change_abs": 3.75,
      "volume": 50000000,
      "Recommend.All": 0.8,
      "market_cap_basic": 2500000000000,
      "price_earnings_ttm": 25.5,
      "earnings_per_share_basic_ttm": 6.0
    }
  ],
  "total": 1,
  "totalCount": 1500
}
```

## 10. Finding Symbol Markets

The Symbol Markets feature allows you to discover all exchanges and markets where a specific symbol is traded.

#### Basic Symbol Market Search
```python
from tradingview_scraper.symbols.symbol_markets import SymbolMarkets

markets = SymbolMarkets()

# Find all markets where AAPL is traded
aapl_markets = markets.scrape(symbol='AAPL')

print(f"AAPL is traded on {aapl_markets['total']} markets")
print("Markets:", aapl_markets['data'])
```

#### Regional Market Search
```python
from tradingview_scraper.symbols.symbol_markets import SymbolMarkets

markets = SymbolMarkets()

# Find only US markets
us_markets = markets.scrape(
    symbol='AAPL',
    scanner='america'
)

print("US Markets:", us_markets['data'])
```

#### Crypto Symbol Markets
```python
from tradingview_scraper.symbols.symbol_markets import SymbolMarkets

markets = SymbolMarkets()

# Find all crypto exchanges trading Bitcoin
btc_markets = markets.scrape(
    symbol='BTCUSD',
    scanner='crypto',
    limit=100
)

print(f"Bitcoin is traded on {btc_markets['total']} crypto exchanges")
```

#### Custom Columns
```python
from tradingview_scraper.symbols.symbol_markets import SymbolMarkets

markets = SymbolMarkets()

# Get specific information only
custom_markets = markets.scrape(
    symbol='TSLA',
    columns=['name', 'close', 'volume', 'exchange', 'currency'],
    limit=50
)

for market in custom_markets['data']:
    print(f"{market['exchange']}: {market['close']} {market.get('currency', 'N/A')}")
```

#### Supported Scanners
- `global`: Search across all markets worldwide (default)
- `america`: US stock markets
- `crypto`: Cryptocurrency exchanges
- `forex`: Forex markets
- `cfd`: CFD markets

#### Output Example:
```json
{
  "status": "success",
  "data": [
    {
      "symbol": "NASDAQ:AAPL",
      "name": "AAPL",
      "close": 150.25,
      "change": 2.5,
      "change_abs": 3.75,
      "volume": 50000000,
      "exchange": "NASDAQ",
      "type": "stock",
      "description": "Apple Inc.",
      "currency": "USD",
      "market_cap_basic": 2500000000000
    },
    {
      "symbol": "GPW:AAPL",
      "name": "AAPL",
      "close": 148.50,
      "change": 1.2,
      "change_abs": 1.80,
      "volume": 1000000,
      "exchange": "GPW",
      "type": "stock",
      "description": "Apple Inc.",
      "currency": "PLN",
      "market_cap_basic": 2500000000000
    }
  ],
  "total": 2,
  "totalCount": 87
}
```

### Section 11: Markets Overview

Get top stocks by various criteria from different markets:

#### Get Top Stocks by Market Cap
```python
from tradingview_scraper.symbols.markets import Markets

markets = Markets()

# Get top 20 stocks by market capitalization from US market
top_by_cap = markets.get_top_stocks(
    market='america',
    by='market_cap',
    limit=20
)

print("Top Stocks by Market Cap:")
for stock in top_by_cap['data']:
    print(f"{stock['name']}: ${stock['market_cap_basic']:,.0f}")
```

#### Get Most Active Stocks
```python
from tradingview_scraper.symbols.markets import Markets

markets = Markets()

# Get top 30 stocks by trading volume
most_active = markets.get_top_stocks(
    market='america',
    by='volume',
    limit=30
)

print("Most Active Stocks:")
for stock in most_active['data']:
    print(f"{stock['name']}: Volume {stock['volume']:,.0f}")
```

#### Get Biggest Movers
```python
from tradingview_scraper.symbols.markets import Markets

markets = Markets()

# Get top 25 stocks by price change
biggest_movers = markets.get_top_stocks(
    market='america',
    by='change',
    limit=25
)

print("Biggest Movers:")
for stock in biggest_movers['data']:
    print(f"{stock['name']}: {stock['change']:.2f}%")
```

#### Get Top Stocks with Custom Columns
```python
from tradingview_scraper.symbols.markets import Markets

markets = Markets()

# Get top stocks with specific data fields
custom_columns = [
    'name',
    'close',
    'volume',
    'market_cap_basic',
    'price_earnings_ttm',
    'sector',
    'industry'
]

custom_results = markets.get_top_stocks(
    market='america',
    by='market_cap',
    columns=custom_columns,
    limit=10
)

print("Top Stocks with Custom Data:")
for stock in custom_results['data']:
    print(f"{stock['name']}: ${stock['close']} | P/E: {stock.get('price_earnings_ttm', 'N/A')}")
```

#### Supported Markets
- `america`: US Stock Market
- `australia`: Australian Stock Market
- `canada`: Canadian Stock Market
- `germany`: German Stock Market
- `india`: Indian Stock Market
- `uk`: UK Stock Market
- `crypto`: Cryptocurrency Market
- `forex`: Forex Market
- `global`: Global Market

#### Supported Sort Criteria
- `market_cap`: Sort by market capitalization
- `volume`: Sort by trading volume
- `change`: Sort by price change percentage
- `price`: Sort by current price
- `volatility`: Sort by volatility

#### Output Example:
```json
{
  "status": "success",
  "data": [
    {
      "symbol": "NASDAQ:NVDA",
      "name": "NVDA",
      "close": 875.50,
      "change": 3.25,
      "change_abs": 27.50,
      "volume": 45000000,
      "Recommend.All": 0.8,
      "market_cap_basic": 2200000000000,
      "price_earnings_ttm": 45.5,
      "earnings_per_share_basic_ttm": 19.25,
      "sector": "Technology",
      "industry": "Semiconductors"
    }
  ],
  "total": 1,
  "totalCount": 5000
}
```

### Section 12: Symbol Overview

Get comprehensive overview data for any symbol:

#### Get Complete Overview Data
```python
from tradingview_scraper.symbols.overview import Overview

overview = Overview()

# Get full overview for Apple stock
aapl = overview.get_symbol_overview(symbol='NASDAQ:AAPL')

print("Company:", aapl['data']['description'])
print("Price:", aapl['data']['close'])
print("Market Cap:", aapl['data']['market_cap_basic'])
print("P/E Ratio:", aapl['data']['price_earnings_ttm'])
print("Sector:", aapl['data']['sector'])
```

#### Get Profile Information
```python
from tradingview_scraper.symbols.overview import Overview

overview = Overview()

# Get basic profile for a symbol
profile = overview.get_profile(symbol='NASDAQ:AAPL')

print("Profile Data:")
print(f"Name: {profile['data']['name']}")
print(f"Description: {profile['data']['description']}")
print(f"Exchange: {profile['data']['exchange']}")
print(f"Sector: {profile['data']['sector']}")
print(f"Industry: {profile['data']['industry']}")
print(f"Country: {profile['data']['country']}")
```

#### Get Statistics and Valuation
```python
from tradingview_scraper.symbols.overview import Overview

overview = Overview()

# Get market statistics and valuation ratios
stats = overview.get_statistics(symbol='NASDAQ:AAPL')

print("Statistics:")
print(f"Market Cap: ${stats['data']['market_cap_basic']:,.0f}")
print(f"P/E Ratio: {stats['data']['price_earnings_ttm']:.2f}")
print(f"P/B Ratio: {stats['data']['price_book_fq']:.2f}")
print(f"EPS: ${stats['data']['earnings_per_share_basic_ttm']:.2f}")
print(f"Dividend Yield: {stats['data']['dividends_yield']:.2%}")
```

#### Get Financial Metrics
```python
from tradingview_scraper.symbols.overview import Overview

overview = Overview()

# Get financial data
financials = overview.get_financials(symbol='NASDAQ:AAPL')

print("Financials:")
print(f"Revenue: ${financials['data']['total_revenue']:,.0f}")
print(f"Net Income: ${financials['data']['net_income_fy']:,.0f}")
print(f"Operating Margin: {financials['data']['operating_margin_ttm']:.2f}%")
print(f"ROE: {financials['data']['return_on_equity_fq']:.2f}%")
print(f"ROA: {financials['data']['return_on_assets_fq']:.2f}%")
print(f"Debt/Equity: {financials['data']['debt_to_equity_fq']:.2f}")
```

#### Get Performance Metrics
```python
from tradingview_scraper.symbols.overview import Overview

overview = Overview()

# Get performance data
performance = overview.get_performance(symbol='NASDAQ:AAPL')

print("Performance:")
print(f"1 Week: {performance['data']['Perf.W']:.2f}%")
print(f"1 Month: {performance['data']['Perf.1M']:.2f}%")
print(f"3 Months: {performance['data']['Perf.3M']:.2f}%")
print(f"6 Months: {performance['data']['Perf.6M']:.2f}%")
print(f"1 Year: {performance['data']['Perf.Y']:.2f}%")
print(f"YTD: {performance['data']['Perf.YTD']:.2f}%")
```

#### Get Technical Indicators
```python
from tradingview_scraper.symbols.overview import Overview

overview = Overview()

# Get technical indicators
technicals = overview.get_technicals(symbol='NASDAQ:AAPL')

print("Technical Indicators:")
print(f"RSI: {technicals['data']['RSI']:.2f}")
print(f"MACD: {technicals['data']['MACD.macd']:.2f}")
print(f"ADX: {technicals['data']['ADX']:.2f}")
print(f"Recommendation: {technicals['data']['Recommend.All']:.2f}")
print(f"Daily Volatility: {technicals['data']['Volatility.D']:.2f}%")
print(f"Beta: {technicals['data']['beta_1_year']:.2f}")
```

#### Get Crypto Overview
```python
from tradingview_scraper.symbols.overview import Overview

overview = Overview()

# Get Bitcoin overview
btc = overview.get_symbol_overview(symbol='BITSTAMP:BTCUSD')

print("Bitcoin Overview:")
print(f"Price: ${btc['data']['close']:,.2f}")
print(f"24h Change: {btc['data']['change']:.2f}%")
print(f"Volume: ${btc['data']['volume']:,.0f}")
print(f"Market Cap: ${btc['data']['market_cap_basic']:,.0f}")
```

#### Get Custom Fields
```python
from tradingview_scraper.symbols.overview import Overview

overview = Overview()

# Get specific fields only
custom_fields = [
    'name',
    'close',
    'volume',
    'market_cap_basic',
    'price_earnings_ttm',
    'dividends_yield',
    'Perf.Y',
    'RSI'
]

result = overview.get_symbol_overview(
    symbol='NASDAQ:AAPL',
    fields=custom_fields
)

print("Custom Data:", result['data'])
```

#### Supported Symbols
All symbols must include exchange prefix:
- Stocks: `NASDAQ:AAPL`, `NYSE:TSLA`, `LSE:VOD`
- Crypto: `BITSTAMP:BTCUSD`, `BINANCE:BTCUSDT`
- Forex: `FX:EURUSD`, `OANDA:GBPUSD`
- Indices: `SP:SPX`, `DJ:DJI`
- Commodities: `COMEX:GC1!`, `NYMEX:CL1!`

#### Available Field Categories
- **BASIC_FIELDS**: name, description, type, exchange, country, sector, industry
- **PRICE_FIELDS**: close, change, high, low, open, volume, 52-week highs/lows
- **MARKET_FIELDS**: market cap, shares outstanding, float, diluted shares
- **VALUATION_FIELDS**: P/E, P/B, P/S, P/FCF, EPS ratios
- **DIVIDEND_FIELDS**: yield, per share, payout ratio
- **FINANCIAL_FIELDS**: revenue, income, margins, returns, ratios, EBITDA, employees
- **PERFORMANCE_FIELDS**: weekly, monthly, quarterly, yearly returns
- **VOLATILITY_FIELDS**: daily/weekly/monthly volatility, beta
- **TECHNICAL_FIELDS**: RSI, MACD, ADX, CCI, Stoch.K, recommendations

#### Output Example:
```json
{
  "status": "success",
  "data": {
    "symbol": "NASDAQ:AAPL",
    "name": "AAPL",
    "description": "Apple Inc.",
    "close": 267.66,
    "change": -0.78,
    "volume": 26882593,
    "market_cap_basic": 3955022105550,
    "price_earnings_ttm": 35.88,
    "earnings_per_share_basic_ttm": 7.49,
    "dividends_yield": 0.39,
    "sector": "Electronic Technology",
    "industry": "Telecommunications Equipment",
    "country": "United States",
    "Perf.Y": 19.16,
    "RSI": 61.90,
    "Recommend.All": 0.22,
    "beta_1_year": 1.19
  }
}
```

### Section 13: Minds Community Discussions

Get community discussions, questions, and trading ideas:

#### Get Recent Discussions
```python
from tradingview_scraper.symbols.minds import Minds

minds = Minds()

# Get recent discussions for Apple
aapl_minds = minds.get_minds(
    symbol='NASDAQ:AAPL',
    sort='recent',
    limit=20
)

print(f"Found {aapl_minds['total']} discussions")
for discussion in aapl_minds['data']:
    print(f"\n{discussion['author']['username']}: {discussion['text'][:100]}...")
    print(f"Likes: {discussion['total_likes']}, Comments: {discussion['total_comments']}")
```

#### Get Popular Discussions
```python
from tradingview_scraper.symbols.minds import Minds

minds = Minds()

# Get popular discussions sorted by engagement
popular = minds.get_minds(
    symbol='NASDAQ:TSLA',
    sort='popular',
    limit=15
)

print("Popular Discussions:")
for item in popular['data']:
    print(f"\nAuthor: {item['author']['username']}")
    print(f"Text: {item['text']}")
    print(f"Engagement: {item['total_likes']} likes, {item['total_comments']} comments")
    print(f"Created: {item['created']}")
```

#### Get Trending Discussions
```python
from tradingview_scraper.symbols.minds import Minds

minds = Minds()

# Get trending discussions
trending = minds.get_minds(
    symbol='BITSTAMP:BTCUSD',
    sort='trending',
    limit=25
)

print("Trending Bitcoin Discussions:")
for discussion in trending['data']:
    print(f"\n{discussion['text']}")
    print(f"Author: {discussion['author']['username']}")
    print(f"Profile: {discussion['author']['profile_url']}")
```

#### Get All Discussions with Pagination
```python
from tradingview_scraper.symbols.minds import Minds

minds = Minds()

# Get all available discussions (up to max_results)
all_discussions = minds.get_all_minds(
    symbol='NASDAQ:AAPL',
    sort='popular',
    max_results=100
)

print(f"Retrieved {all_discussions['total']} discussions across {all_discussions['pages']} pages")

# Analyze sentiment
total_likes = sum(d['total_likes'] for d in all_discussions['data'])
print(f"Total community likes: {total_likes}")
```

#### Access Symbol Information
```python
from tradingview_scraper.symbols.minds import Minds

minds = Minds()

result = minds.get_minds(symbol='NASDAQ:AAPL', limit=10)

# Symbol information included in response
symbol_info = result['symbol_info']
print(f"Symbol: {symbol_info.get('short_name')}")
print(f"Exchange: {symbol_info.get('exchange')}")
print(f"Type: {symbol_info.get('type')}")
print(f"Name: {symbol_info.get('instrument_name')}")
```

#### Filter by User Activity
```python
from tradingview_scraper.symbols.minds import Minds

minds = Minds()

# Get discussions
discussions = minds.get_minds(symbol='NASDAQ:AAPL', limit=50)

# Filter high-engagement posts
high_engagement = [
    d for d in discussions['data']
    if d['total_likes'] > 10 or d['total_comments'] > 5
]

print(f"High engagement posts: {len(high_engagement)}")
for post in high_engagement:
    print(f"\n{post['text'][:100]}...")
    print(f"Engagement: {post['total_likes']} likes, {post['total_comments']} comments")
```

#### Export Discussions
```python
from tradingview_scraper.symbols.minds import Minds

# Enable export to JSON
minds = Minds(export_result=True, export_type='json')

# Get and export discussions
discussions = minds.get_minds(
    symbol='NASDAQ:AAPL',
    sort='popular',
    limit=100
)

print(f"Exported {discussions['total']} discussions to JSON file")
```

#### Supported Symbols
All symbols must include exchange prefix:
- Stocks: `NASDAQ:AAPL`, `NYSE:TSLA`, `LSE:VOD`
- Crypto: `BITSTAMP:BTCUSD`, `BINANCE:BTCUSDT`
- Forex: `FX:EURUSD`, `OANDA:GBPUSD`
- Indices: `SP:SPX`, `DJ:DJI`

#### Sort Options
- `recent`: Most recent discussions (default)
- `popular`: Sorted by total engagement (likes + comments)
- `trending`: Currently trending discussions

#### Output Example:
```json
{
  "status": "success",
  "data": [
    {
      "uid": "abc123xyz",
      "text": "$AAPL looking strong above 270. Potential breakout incoming!",
      "url": "https://www.tradingview.com/symbols/NASDAQ-AAPL/minds/?mind=abc123xyz",
      "author": {
        "username": "trader123",
        "profile_url": "https://www.tradingview.com/u/trader123/",
        "is_broker": false
      },
      "created": "2025-11-07 16:47:45",
      "symbols": ["NASDAQ:AAPL"],
      "total_likes": 15,
      "total_comments": 8,
      "modified": false,
      "hidden": false
    }
  ],
  "total": 1,
  "symbol_info": {
    "short_name": "AAPL",
    "exchange": "NASDAQ",
    "type": "stock",
    "instrument_name": "Apple Inc"
  },
  "next_cursor": "cursor_string_for_pagination"
}
```

### 14. Fundamental Financial Data

The `FundamentalGraphs` class provides comprehensive fundamental financial data for stocks and other securities. Access income statements, balance sheets, cash flow data, profitability ratios, and valuation metrics.

#### Get Complete Fundamental Data
```python
from tradingview_scraper.symbols.fundamental_graphs import FundamentalGraphs

fundamentals = FundamentalGraphs()

# Get all fundamental data for Apple
aapl_data = fundamentals.get_fundamentals(symbol='NASDAQ:AAPL')

if aapl_data['status'] == 'success':
    data = aapl_data['data']
    print(f"Revenue: ${data.get('total_revenue', 'N/A'):,.0f}")
    print(f"Net Income: ${data.get('net_income', 'N/A'):,.0f}")
    print(f"EBITDA: ${data.get('EBITDA', 'N/A'):,.0f}")
    print(f"Market Cap: ${data.get('market_cap_basic', 'N/A'):,.0f}")
    print(f"P/E Ratio: {data.get('price_earnings_ttm', 'N/A')}")
```

#### Get Income Statement Data
```python
from tradingview_scraper.symbols.fundamental_graphs import FundamentalGraphs

fundamentals = FundamentalGraphs()

# Get income statement for Apple
income_data = fundamentals.get_income_statement(symbol='NASDAQ:AAPL')

data = income_data['data']
print(f"Total Revenue: ${data.get('total_revenue', 'N/A'):,.0f}")
print(f"Gross Profit: ${data.get('gross_profit', 'N/A'):,.0f}")
print(f"Operating Income: ${data.get('operating_income', 'N/A'):,.0f}")
print(f"Net Income: ${data.get('net_income', 'N/A'):,.0f}")
print(f"EPS (Basic): ${data.get('earnings_per_share_basic_ttm', 'N/A'):.2f}")
print(f"EPS (Diluted): ${data.get('earnings_per_share_diluted_ttm', 'N/A'):.2f}")
```

#### Get Balance Sheet Data
```python
from tradingview_scraper.symbols.fundamental_graphs import FundamentalGraphs

fundamentals = FundamentalGraphs()

# Get balance sheet for Microsoft
balance_data = fundamentals.get_balance_sheet(symbol='NASDAQ:MSFT')

data = balance_data['data']
print(f"Total Assets: ${data.get('total_assets', 'N/A'):,.0f}")
print(f"Cash & Short-term Investments: ${data.get('cash_n_short_term_invest', 'N/A'):,.0f}")
print(f"Total Debt: ${data.get('total_debt', 'N/A'):,.0f}")
print(f"Stockholders Equity: ${data.get('stockholders_equity', 'N/A'):,.0f}")
print(f"Book Value per Share: ${data.get('book_value_per_share_fq', 'N/A'):.2f}")
```

#### Get Cash Flow Data
```python
from tradingview_scraper.symbols.fundamental_graphs import FundamentalGraphs

fundamentals = FundamentalGraphs()

# Get cash flow for Google
cash_flow_data = fundamentals.get_cash_flow(symbol='NASDAQ:GOOGL')

data = cash_flow_data['data']
print(f"Operating Activities: ${data.get('cash_f_operating_activities', 'N/A'):,.0f}")
print(f"Investing Activities: ${data.get('cash_f_investing_activities', 'N/A'):,.0f}")
print(f"Financing Activities: ${data.get('cash_f_financing_activities', 'N/A'):,.0f}")
print(f"Free Cash Flow: ${data.get('free_cash_flow', 'N/A'):,.0f}")
```

#### Get Profitability Ratios
```python
from tradingview_scraper.symbols.fundamental_graphs import FundamentalGraphs

fundamentals = FundamentalGraphs()

# Get profitability metrics
profitability = fundamentals.get_profitability(symbol='NASDAQ:AAPL')

data = profitability['data']
print(f"Return on Equity (ROE): {data.get('return_on_equity_fq', 'N/A'):.2%}")
print(f"Return on Assets (ROA): {data.get('return_on_assets_fq', 'N/A'):.2%}")
print(f"Return on Investment (ROI): {data.get('return_on_investment_ttm', 'N/A'):.2%}")
```

#### Get Margin Metrics
```python
from tradingview_scraper.symbols.fundamental_graphs import FundamentalGraphs

fundamentals = FundamentalGraphs()

# Get margin data
margins = fundamentals.get_margins(symbol='NASDAQ:AAPL')

data = margins['data']
print(f"Gross Margin: {data.get('gross_margin_percent_ttm', 'N/A'):.2%}")
print(f"Operating Margin: {data.get('operating_margin_ttm', 'N/A'):.2%}")
print(f"Net Margin: {data.get('net_margin_percent_ttm', 'N/A'):.2%}")
print(f"EBITDA Margin: {data.get('EBITDA_margin', 'N/A'):.2%}")
```

#### Get Liquidity & Leverage Ratios
```python
from tradingview_scraper.symbols.fundamental_graphs import FundamentalGraphs

fundamentals = FundamentalGraphs()

# Get liquidity ratios
liquidity = fundamentals.get_liquidity(symbol='NASDAQ:AAPL')
print(f"Current Ratio: {liquidity['data'].get('current_ratio_fq', 'N/A'):.2f}")
print(f"Quick Ratio: {liquidity['data'].get('quick_ratio_fq', 'N/A'):.2f}")

# Get leverage ratios
leverage = fundamentals.get_leverage(symbol='NASDAQ:AAPL')
print(f"Debt-to-Equity: {leverage['data'].get('debt_to_equity_fq', 'N/A'):.2f}")
print(f"Debt-to-Assets: {leverage['data'].get('debt_to_assets', 'N/A'):.2f}")
```

#### Get Valuation Metrics
```python
from tradingview_scraper.symbols.fundamental_graphs import FundamentalGraphs

fundamentals = FundamentalGraphs()

# Get valuation data
valuation = fundamentals.get_valuation(symbol='NASDAQ:AAPL')

data = valuation['data']
print(f"Market Cap: ${data.get('market_cap_basic', 'N/A'):,.0f}")
print(f"Enterprise Value: ${data.get('enterprise_value_fq', 'N/A'):,.0f}")
print(f"P/E Ratio: {data.get('price_earnings_ttm', 'N/A'):.2f}")
print(f"P/B Ratio: {data.get('price_book_fq', 'N/A'):.2f}")
print(f"P/S Ratio: {data.get('price_sales_ttm', 'N/A'):.2f}")
print(f"P/FCF Ratio: {data.get('price_free_cash_flow_ttm', 'N/A'):.2f}")
```

#### Get Dividend Information
```python
from tradingview_scraper.symbols.fundamental_graphs import FundamentalGraphs

fundamentals = FundamentalGraphs()

# Get dividend data
dividends = fundamentals.get_dividends(symbol='NASDAQ:AAPL')

data = dividends['data']
print(f"Dividend Yield: {data.get('dividends_yield', 'N/A'):.2%}")
print(f"Dividends per Share: ${data.get('dividends_per_share_fq', 'N/A'):.2f}")
print(f"Payout Ratio: {data.get('dividend_payout_ratio_ttm', 'N/A'):.2%}")
```

#### Compare Multiple Symbols
```python
from tradingview_scraper.symbols.fundamental_graphs import FundamentalGraphs

fundamentals = FundamentalGraphs()

# Compare fundamental metrics across tech giants
comparison = fundamentals.compare_fundamentals(
    symbols=['NASDAQ:AAPL', 'NASDAQ:MSFT', 'NASDAQ:GOOGL'],
    fields=['total_revenue', 'net_income', 'EBITDA', 'market_cap_basic', 'price_earnings_ttm']
)

if comparison['status'] == 'success':
    # Access comparison data
    for field, values in comparison['comparison'].items():
        print(f"\n{field}:")
        for symbol, value in values.items():
            print(f"  {symbol}: {value:,.0f}" if isinstance(value, (int, float)) else f"  {symbol}: {value}")
```

#### Get Custom Fields
```python
from tradingview_scraper.symbols.fundamental_graphs import FundamentalGraphs

fundamentals = FundamentalGraphs()

# Get only specific fundamental fields
custom_data = fundamentals.get_fundamentals(
    symbol='NASDAQ:AAPL',
    fields=[
        'total_revenue',
        'net_income',
        'free_cash_flow',
        'return_on_equity_fq',
        'debt_to_equity_fq',
        'price_earnings_ttm'
    ]
)

print("Selected Metrics:")
for field, value in custom_data['data'].items():
    if field != 'symbol':
        print(f"{field}: {value}")
```

#### Export Fundamental Data
```python
from tradingview_scraper.symbols.fundamental_graphs import FundamentalGraphs

# Enable export to JSON
fundamentals = FundamentalGraphs(export_result=True, export_type='json')

# Get and export fundamental data
data = fundamentals.get_fundamentals(symbol='NASDAQ:AAPL')

print(f"Exported fundamental data for {data['data']['symbol']}")
```

#### Supported Symbols
All symbols must include exchange prefix:
- Stocks: `NASDAQ:AAPL`, `NYSE:JPM`, `LSE:VOD`
- No support for crypto, forex, or other non-stock symbols

#### Available Field Categories
- **Income Statement**: revenue, profit, earnings, EBITDA
- **Balance Sheet**: assets, debt, equity, cash
- **Cash Flow**: operating, investing, financing activities, free cash flow
- **Profitability**: ROE, ROA, ROI
- **Liquidity**: current ratio, quick ratio
- **Leverage**: debt-to-equity, debt-to-assets
- **Margins**: gross, operating, net, EBITDA margins
- **Valuation**: market cap, enterprise value, P/E, P/B, P/S
- **Dividends**: yield, per share, payout ratio

#### Output Example:
```json
{
  "status": "success",
  "data": {
    "symbol": "NASDAQ:AAPL",
    "total_revenue": 394328000000,
    "net_income": 100913000000,
    "EBITDA": 130541000000,
    "total_assets": 365725000000,
    "total_debt": 101304000000,
    "stockholders_equity": 62146000000,
    "cash_f_operating_activities": 116433000000,
    "free_cash_flow": 106496000000,
    "return_on_equity_fq": 1.6233,
    "current_ratio_fq": 0.94,
    "debt_to_equity_fq": 1.63,
    "gross_margin_percent_ttm": 0.4607,
    "operating_margin_ttm": 0.3096,
    "net_margin_percent_ttm": 0.2559,
    "market_cap_basic": 3550000000000,
    "price_earnings_ttm": 35.19,
    "dividends_yield": 0.0044
  }
}
```

## Changes:
- Release `0.4.19`:
  Fix raise error while fetching ideas for pages greater than 1
- Release `0.4.17`:
  Add Fundamental Graphs feature for comprehensive financial data
  Support 9 field categories: income statement, balance sheet, cash flow, profitability, liquidity, leverage, margins, valuation, dividends
  Helper methods for specific financial statements (get_income_statement, get_balance_sheet, get_cash_flow, etc.)
  Multi-symbol comparison with compare_fundamentals() method
  Support for 60+ fundamental metrics per symbol
- Release `0.4.16`:
  Add Minds feature for community discussions and trading ideas
  Support recent, popular, and trending sort options
  Pagination support with get_all_minds() method
  User engagement metrics (likes, comments) and author information
- Release `0.4.15`:
  Add Symbol Overview feature for comprehensive symbol data
  Support for profile, statistics, financials, performance, and technical data
  9 field categories with 70+ data points per symbol
  Helper methods for specific data categories
- Release `0.4.14`:
  Add Markets Overview feature for top stocks analysis
  Sort by market cap, volume, change, price, volatility
  Support 9 markets (America, Australia, Canada, Germany, India, UK, Crypto, Forex, Global)
- Release `0.4.13`:
  Add Symbol Markets feature to find all exchanges/markets where a symbol is traded
  Support global, regional (America, Crypto, Forex, CFD) market scanners
  Discover stocks, crypto, derivatives across 100+ exchanges worldwide
- Release `0.4.12`:
  Add Screener functionality with custom filters, sorting, and column selection
  Support 18 markets (America, Canada, Germany, India, UK, Crypto, Forex, CFD, Futures, Bonds, etc.)
  Support 15+ filter operations (greater, less, equal, in_range, crosses, etc.)
- Release `0.4.11`:
  Add Market Movers scraper (Gainers, Losers, Penny Stocks, Pre-market/After-hours movers)
  Support multiple markets (USA, UK, India, Australia, Canada, Crypto, Forex, Bonds, Futures)
- Release `0.4.9`:
  Add [documentation](https://mnwato.github.io/tradingview-scraper/)
- Release `0.4.8`:
  Fix bug while fetching ADX+DI indicators
  Add timeframe param for streamer export data
- Release `0.4.7`:
  Fix bug undefined RealTimeData class
- Release `0.4.6`:
  Add value argument to specify calander fields
  Add Streamer class for getting OHLCV and indicator simultaneously
  Integrate realtime data and historical exporter into Streamer class
- Release `0.4.2`:
  Add calander (Dividend, Earning)
  Make requirements non-explicit
  Lint fix
  Add tests (ideas, realtime_price, indicators)
  Add reconnection method for realtime price scraper
- Release `0.4.0`:
  Update exchange list
  Add real-time price streaming
- Release `0.3.2`:  
  Support timeframe to get Indicators
- Release `0.3.0`:   
  Add news scraper
- Release `0.2.9`:   
  Refactor for new TradingView structure
- Release `0.1.0`:  
  The name of `ClassA` changed to `Ideas`

### 9. Institutional Quantitative Workflow (V2)

The library now includes a full-lifecycle quantitative pipeline designed for professional trading desk oversight.

#### Implementation Dashboard (CLI)
Instantly view optimized allocations and trend candidates directly in your terminal with beautiful formatting.
```bash
make display
```

#### Production Lifecycle
Run the entire pipeline—from discovery to de-risked allocation—with institutional reproducibility:
```bash
# Run the institutional production pipeline (Default)
make daily-run

# Run a lightweight development test
make daily-run PROFILE=repro_dev

# Run the multi-engine benchmarking tournament
make tournament
```

**Key Capabilities:**
*   **Multi-Factor Regime Detection**: Entropy, DWT Spectral Turbulence, and Volatility Clustering.
*   **Hierarchical Risk Bucketing**: Automatic redundancy filtering (e.g., 70+ crypto tickers behave as one unit).
*   **Cluster-Aware Optimization**: Strictly enforced 25% global concentration caps and **CVaR-penalized** objectives.
*   **Self-Healing Data Layer**: Automated gap detection and targeted repair for 200-day alignment.
*   **Decision Trail Audit**: Full post-mortem logs (`selection_audit.md`) documenting every universe pruning and allocation choice.
*   **High-Fidelity Simulation**: Professional friction modeling (slippage/commissions) via integrated **CVXPortfolio** simulator.
*   **Multi-Engine Benchmarking**: Integrated "Tournament Mode" comparing `skfolio`, `Riskfolio-Lib`, `PyPortfolioOpt`, and `cvxportfolio` across idealized and high-fidelity simulators.
*   **Markdown Tear-sheets**: Automated generation of strategy performance teardowns (Sharpe, Sortino, Drawdown audits) using **QuantStats**.
*   **JSON Manifest Control**: Reproducible workflow profiles via schema-validated `manifest.json`.
*   **Live Output Example**: [Institutional Portfolio Implementation Gist](https://gist.github.com/tommy-ca/e888e1eab0b86447c90c26e92ec4dc36)

---

## License:

```
[MIT]
```
