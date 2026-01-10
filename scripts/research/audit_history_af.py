import os

import pandas as pd


def audit_history_vs_af():
    returns_path = "data/lakehouse/portfolio_returns.pkl"
    af_path = "data/lakehouse/antifragility_stats.json"

    if not os.path.exists(returns_path) or not os.path.exists(af_path):
        print("Data missing.")
        return

    df = pd.read_pickle(returns_path)
    af_stats = pd.read_json(af_path).set_index("Symbol")

    audit = []
    for symbol in df.columns:
        history_len = df[symbol].count()
        af_score = af_stats.loc[symbol, "Antifragility_Score"] if symbol in af_stats.index else None
        skew = af_stats.loc[symbol, "Skew"] if symbol in af_stats.index else None

        audit.append({"Symbol": symbol, "History_Days": history_len, "AF_Score": af_score, "Skew": skew})

    audit_df = pd.DataFrame(audit).sort_values("History_Days")
    print(audit_df.to_markdown(index=False))


if __name__ == "__main__":
    audit_history_vs_af()
