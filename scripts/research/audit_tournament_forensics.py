import json
import logging
from pathlib import Path

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("tournament_forensics")


def load_audit_data(run_id: str) -> pd.DataFrame:
    path = Path(f"artifacts/summaries/runs/{run_id}/audit.jsonl")
    if not path.exists():
        logger.error(f"Audit ledger not found at {path}")
        return pd.DataFrame()

    rows = []
    with open(path, "r") as f:
        for line in f:
            try:
                data = json.loads(line)
                if data.get("step") == "backtest_simulate" and data.get("status") == "success":
                    ctx = data.get("context", {})
                    outcome = data.get("outcome", {})
                    metrics = outcome.get("metrics", {})

                    rows.append(
                        {
                            "selection": ctx.get("selection_mode"),
                            "rebalance": ctx.get("rebalance_mode"),
                            "simulator": ctx.get("simulator"),
                            "engine": ctx.get("engine"),
                            "profile": ctx.get("profile"),
                            "window": ctx.get("window_index"),
                            "sharpe": metrics.get("sharpe"),
                            "return": metrics.get("return"),
                            "vol": metrics.get("vol"),
                            "kappa": ctx.get("kappa", 1.0),
                        }
                    )
            except Exception:
                continue

    return pd.DataFrame(rows)


def audit_outliers(df: pd.DataFrame):
    if df.empty:
        return

    logger.info("\n--- 1. Simulator Friction Audit ---")
    # Compare custom vs cvxportfolio per (selection, rebalance, engine, profile)
    # Average across windows
    summary = df.groupby(["selection", "rebalance", "simulator", "engine", "profile"])["sharpe"].mean().unstack("simulator")

    if "custom" in summary.columns and "cvxportfolio" in summary.columns:
        summary["friction_decay"] = (summary["cvxportfolio"] / summary["custom"]) - 1
        outliers = summary[summary["friction_decay"] < -0.3].sort_values("friction_decay")
        if not outliers.empty:
            logger.warning(f"Found {len(outliers)} configurations with >30% Sharpe decay in High-Fidelity:")
            print(outliers[["custom", "cvxportfolio", "friction_decay"]].head(10))
        else:
            logger.info("No extreme friction outliers found (<30% decay).")

    logger.info("\n--- 2. Temporal Consistency Audit ---")
    # Standard deviation of Sharpe across windows for top configs
    win_stats = df.groupby(["selection", "rebalance", "simulator", "engine", "profile"])["sharpe"].agg(["mean", "std", "count"])
    win_stats["cv"] = win_stats["std"] / win_stats["mean"].abs()

    top_configs = win_stats[win_stats["mean"] > 3.0].sort_values("cv", ascending=False)
    if not top_configs.empty:
        logger.warning("Top configurations with high window-to-window variance (CV > 0.5):")
        print(top_configs[top_configs["cv"] > 0.5].head(10))
    else:
        logger.info("Top configurations show good temporal consistency.")

    logger.info("\n--- 3. Numerical Stability Audit ---")
    # Correlation between kappa and return
    corrs = df.groupby(["engine", "profile"]).apply(lambda x: x["kappa"].corr(x["return"]))
    unstable = corrs[corrs.abs() > 0.5]
    if not unstable.empty:
        logger.warning("Strategies where returns are highly correlated with matrix ill-conditioning (|corr| > 0.5):")
        print(unstable)
    else:
        logger.info("No strong correlation found between ill-conditioning and performance.")


def main():
    run_id = "20260104-005636"
    df = load_audit_data(run_id)
    if df.empty:
        return

    audit_outliers(df)


if __name__ == "__main__":
    main()
