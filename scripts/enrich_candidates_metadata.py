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

    # Custom Overrides for N/A sectors
    custom_sectors = {
        "NYSE:SPG": "Real Estate (Retail)",
        "NYSE:PLD": "Real Estate (Logistics)",
        "NASDAQ:HST": "Real Estate (Hospitality)",
        "BYBIT:CCUSDT": "Crypto Alpha",
        "OKX:TRUMPUSDT.P": "PolitiFi",
        "OKX:XRPUSDT.P": "Crypto L1",
        "OKX:FILUSDT.P": "Crypto Storage",
        "BINANCE:FILUSDT.P": "Crypto Storage",
        "BINANCE:AVAXUSDT.P": "Crypto L1",
    }

    # Enrich
    enriched_count = 0
    for c in candidates:
        sym = c["symbol"]
        meta = symbol_meta.get(sym)
        if meta:
            c["description"] = meta["description"]
            c["sector"] = meta["sector"]

        # Apply custom overrides if sector is still N/A or empty
        if sym in custom_sectors and (not c.get("sector") or c.get("sector") == "N/A"):
            c["sector"] = custom_sectors[sym]

        if meta or sym in custom_sectors:
            enriched_count += 1

    with open(candidates_path, "w") as f:
        json.dump(candidates, f, indent=2)

    print(f"Enriched {enriched_count}/{len(candidates)} candidates with metadata.")


if __name__ == "__main__":
    enrich_candidates()
