import glob
import json
import os

import pandas as pd

# Proper Quotes Whitelist
ALLOWED_QUOTES = {"USDT", "USDC", "USD", "DAI", "BUSD", "FDUSD"}


def verify_quality():
    files = sorted(glob.glob("export/universe_selector_*_base_*.json"), key=os.path.getmtime, reverse=True)[:8]

    report = []

    for f in files:
        with open(f, "r") as j:
            rows = json.load(j)
            basename = os.path.basename(str(f))
            parts = basename.split("_")
            exchange = parts[2].upper()
            ptype = parts[4].upper()

            if not rows:
                continue

            df = pd.DataFrame(rows)

            # 1. Uniqueness Check
            from tradingview_scraper.futures_universe_selector import FuturesUniverseSelector

            df["base"] = df["symbol"].apply(lambda x: FuturesUniverseSelector._base_symbol(x))
            dupes = df[df.duplicated("base", keep=False)]

            # 2. Quote Compliance
            def get_quote(sym):
                _, q = FuturesUniverseSelector._extract_base_quote(sym)
                return q

            df["quote"] = df["symbol"].apply(get_quote)
            invalid_quotes = df[~df["quote"].isin(ALLOWED_QUOTES)]

            if not invalid_quotes.empty:
                print(f"\n[DEBUG] Invalid quotes in {exchange} {ptype}:")
                print(invalid_quotes[["symbol", "quote"]].to_string(index=False))

            # 3. Liquidity Floor
            min_vt = df["Value.Traded"].min()

            # 4. Junk Detection (High Volume, No Market Cap)
            suspicious = df[(df["market_cap_external"].isna()) & (df["Value.Traded"] > 5e6)]

            report.append(
                {
                    "Universe": f"{exchange} {ptype}",
                    "Size": len(df),
                    "Unique Bases": df["base"].nunique() == len(df),
                    "Duplicate Count": len(dupes) // 2 if not dupes.empty else 0,
                    "Quote Violations": len(invalid_quotes),
                    "Liquidity Floor": f"${min_vt / 1e6:.2f}M",
                    "Suspicious Assets": len(suspicious),
                }
            )

            if not suspicious.empty:
                print(f"\n[WARNING] Suspicious assets in {exchange} {ptype} (High VT, No MC):")
                print(suspicious[["symbol", "Value.Traded"]].to_string(index=False))

    df_report = pd.DataFrame(report)
    print("\n" + "=" * 100)
    print("FINAL UNIVERSE QUALITY VERIFICATION")
    print("=" * 100)
    print(df_report.to_string(index=False))
    print("=" * 100)

    # Final Verdict
    all_unique = df_report["Unique Bases"].all()
    all_quoted = (df_report["Quote Violations"] == 0).all()

    print("\nFinal Integrity Check:")
    print(f"- Absolute Uniqueness: {'PASSED' if all_unique else 'FAILED'}")
    print(f"- Quote Compliance: {'PASSED' if all_quoted else 'FAILED'}")


if __name__ == "__main__":
    verify_quality()
