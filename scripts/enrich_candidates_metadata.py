import glob
import json
import os


def enrich_candidates():
    candidates_path = "data/lakehouse/portfolio_candidates.json"
    if not os.path.exists(candidates_path):
        print("No candidates file found.")
        return

    with open(candidates_path, "r") as f:
        candidates = json.load(f)

    # Load all export data
    export_files = glob.glob("export/universe_selector_*.json")
    symbol_meta = {}

    for f in export_files:
        try:
            with open(f, "r") as j:
                data = json.load(j)
                items = data.get("data", []) if isinstance(data, dict) else data
                for item in items:
                    if isinstance(item, dict) and "symbol" in item:
                        desc = item.get("description") or item.get("name") or "N/A"
                        symbol_meta[item["symbol"]] = {"description": desc, "sector": item.get("sector") or item.get("industry") or "N/A"}
        except Exception:
            continue

    # Load metadata catalog (symbols.parquet) for robust fallbacks.
    catalog_meta = {}
    catalog_path = "data/lakehouse/symbols.parquet"
    if os.path.exists(catalog_path):
        try:
            import pandas as pd  # type: ignore

            df = pd.read_parquet(catalog_path)
            if "symbol" in df.columns:
                keep_cols = [c for c in ["symbol", "description", "sector", "industry", "type", "subtype"] if c in df.columns]
                df = df[keep_cols].drop_duplicates(subset="symbol", keep="last").set_index("symbol")  # type: ignore
                catalog_meta = df.to_dict(orient="index")
        except Exception:
            catalog_meta = {}

    # Custom Overrides for N/A sectors
    custom_sectors = {
        "NYSE:SPG": "Real Estate (Retail)",
        "NYSE:PLD": "Real Estate (Logistics)",
        "NASDAQ:HST": "Real Estate (Hospitality)",
        "NYSE:CPT": "Real Estate (Residential)",
        "NYSE:FRT": "Real Estate (Retail)",
        "NYSE:ARE": "Real Estate (Life Science)",
        "NYSE:AVB": "Real Estate (Residential)",
        "NYSE:BXP": "Real Estate (Office)",
        "NYSE:DLR": "Real Estate (Data Centers)",
        "NYSE:EQR": "Real Estate (Residential)",
        "NYSE:EXR": "Real Estate (Self Storage)",
        "NYSE:MAA": "Real Estate (Residential)",
        "NYSE:PSA": "Real Estate (Self Storage)",
        "NYSE:REG": "Real Estate (Retail)",
        "NYSE:WELL": "Real Estate (Healthcare)",
        "NYSE:WY": "Real Estate (Timber)",
        "NYSE:VTR": "Real Estate (Healthcare)",
        "NYSE:DHI": "Consumer Durables (Homebuilding)",
        "NASDAQ:EQIX": "Real Estate (Data Centers)",
        "BYBIT:CCUSDT": "Crypto Alpha",
        "OKX:TRUMPUSDT.P": "PolitiFi",
        "OKX:XRPUSDT.P": "Crypto L1",
        "OKX:FILUSDT.P": "Crypto Storage",
        "BINANCE:FILUSDT.P": "Crypto Storage",
        "BINANCE:AVAXUSDT.P": "Crypto L1",
        "CBOT:ZC1!": "Commodities (Grains)",
        "OANDA:CORNUSD": "Commodities (Grains)",
        "OANDA:SOYBNUSD": "Commodities (Grains)",
        "OANDA:WHEATUSD": "Commodities (Grains)",
        "COMEX:SI1!": "Metals (Silver)",
        "COMEX:SIH2026": "Metals (Silver)",
        "COMEX:HG1!": "Metals (Copper)",
        "COMEX:HGH2026": "Metals (Copper)",
        "COMEX:HRCH2026": "Metals (Gold)",
        "OANDA:XAUUSD": "Metals (Gold)",
        "OANDA:XCUUSD": "Metals (Copper)",
        "OANDA:US30USD": "Indices (US30)",
        "CME:MBTZ2025": "Crypto (BTC)",
        "THINKMARKETS:EURJPY": "Forex (JPY)",
        "THINKMARKETS:GBPJPY": "Forex (JPY)",
        "THINKMARKETS:CHFJPY": "Forex (JPY)",
        "THINKMARKETS:CADJPY": "Forex (JPY)",
        "THINKMARKETS:AUDJPY": "Forex (JPY)",
        "THINKMARKETS:AUDUSD": "Forex (USD)",
        "AMEX:HYG": "Fixed Income (High Yield)",
        "NASDAQ:TLT": "Fixed Income (Treasury)",
        "AMEX:AGG": "Fixed Income (Aggregate)",
        "NASDAQ:IEF": "Fixed Income (Treasury)",
        "AMEX:LQD": "Fixed Income (Corporate)",
        "NASDAQ:BND": "Fixed Income (Aggregate)",
        "AMEX:GLD": "Metals (Gold)",
        "AMEX:IWM": "Equities (Russell 2000)",
        "AMEX:SPY": "Equities (S&P 500)",
        "NASDAQ:QQQ": "Equities (Nasdaq 100)",
        "AMEX:VTI": "Equities (Total Market)",
        "AMEX:VEA": "Equities (Developed Mkts)",
        "AMEX:VWO": "Equities (Emerging Mkts)",
        "AMEX:DUST": "Metals (Gold Inverse)",
        "AMEX:SH": "Equities (S&P 500 Inverse)",
        "AMEX:SDS": "Equities (S&P 500 Inverse)",
        "NASDAQ:VXUS": "Equities (International)",
    }

    # Enrich
    enriched_count = 0
    for c in candidates:
        sym = c["symbol"]
        updated = False

        meta = symbol_meta.get(sym)
        if meta:
            if (not c.get("description") or c.get("description") == "N/A") and meta.get("description") and meta.get("description") != "N/A":
                c["description"] = meta["description"]
                updated = True
            if (not c.get("sector") or c.get("sector") == "N/A") and meta.get("sector") and meta.get("sector") != "N/A":
                c["sector"] = meta["sector"]
                updated = True

        # Apply custom overrides if sector is still N/A or empty
        if sym in custom_sectors and (not c.get("sector") or c.get("sector") == "N/A"):
            c["sector"] = custom_sectors[sym]
            updated = True

        # Metadata catalog fallback (symbols.parquet)
        if ((not c.get("sector") or c.get("sector") == "N/A") or (not c.get("description") or c.get("description") == "N/A")) and catalog_meta:
            cat = catalog_meta.get(sym, {})

            if not c.get("sector") or c.get("sector") == "N/A":
                industry = str(cat.get("industry") or "").strip()
                subtype = str(cat.get("subtype") or "").strip()
                sector = str(cat.get("sector") or "").strip()

                if subtype == "reit" or "Real Estate Investment Trust" in industry:
                    c["sector"] = "Real Estate (REIT)"
                    updated = True
                elif sector:
                    c["sector"] = sector
                    updated = True
                elif industry:
                    c["sector"] = industry
                    updated = True

            if not c.get("description") or c.get("description") == "N/A":
                desc = str(cat.get("description") or "").strip()
                if desc:
                    c["description"] = desc
                    updated = True

        # Global fallback for crypto / unclassified
        if not c.get("sector") or c.get("sector") == "N/A":
            m = c.get("market", "").upper()
            if any(x in m for x in ["BINANCE", "BITGET", "BYBIT", "OKX", "CRYPTO"]):
                c["sector"] = "Crypto"
                updated = True
            elif "FOREX" in m:
                c["sector"] = "Forex"
                updated = True
            elif "FUTURES" in m:
                c["sector"] = "Futures"
                updated = True

        if updated:
            enriched_count += 1

    with open(candidates_path, "w") as f:
        json.dump(candidates, f, indent=2)

    print(f"Enriched {enriched_count}/{len(candidates)} candidates with metadata.")


if __name__ == "__main__":
    enrich_candidates()
