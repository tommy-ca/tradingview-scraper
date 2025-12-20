# Tech Stack - TradingView Scraper

## Core Language
* **Python (>= 3.8):** The primary programming language for the library.

## Scraping & HTTP
* **requests:** For making synchronous HTTP requests to TradingView.
* **beautifulsoup4:** For parsing and extracting data from HTML responses.

## Data Processing & Validation
* **pandas:** Used for data manipulation and as an export format for structured data.
* **pydantic:** Employed for data validation and settings management.
* **Market Cap Metadata:** External `market_caps_crypto.json` provides global asset ranking for hybrid guards.

## Real-time & WebSockets
* **websockets & websocket-client:** Provide the foundation for real-time data streaming from TradingView.

## Configuration & Tooling
* **python-dotenv:** For managing environment variables and secrets.
* **setuptools:** Used for packaging and distribution.
* **uv:** Employed for fast, reproducible dependency management and locking.

## Quality Assurance
* **pytest:** The testing framework for the project.
* **ruff:** A fast Python linter and formatter, configured via `pyproject.toml`.
