import argparse
import json
import logging
import os

import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("selection_audit")


def audit_selection(run_id=None):
    ledger_path = "data/lakehouse/selection_audit.json"
    if run_id:
        paths = [
            f"artifacts/summaries/runs/{run_id}/data/lakehouse/selection_audit.json",
            f"artifacts/summaries/runs/{run_id}/selection_audit.json",
            f"artifacts/summaries/runs/{run_id}/config/selection_audit.json",
        ]
        for p in paths:
            if os.path.exists(p):
                ledger_path = p
                break

    if not os.path.exists(ledger_path):
        logger.error(f"Ledger not found: {ledger_path}")
        return

    logger.info(f"Auditing Selection Ledger: {ledger_path}")

    with open(ledger_path, "r") as f:
        data = json.load(f)

    n_discovered = 0
    n_selected = 0

    if isinstance(data, dict):
        logger.info(f"Ledger Keys: {list(data.keys())}")

        # 1. Discovery
        discovery = data.get("discovery", {})
        if isinstance(discovery, dict):
            if "categories" in discovery:
                n_discovered = discovery.get("total_symbols_found", 0)
            else:
                n_discovered = len(discovery.get("symbols", []))
        elif isinstance(discovery, list):
            n_discovered = len(discovery)

        logger.info(f"Step 1: Discovery -> {n_discovered} assets")

        # 3. Selection
        selection = data.get("selection", [])
        if isinstance(selection, dict):
            n_selected = selection.get("total_selected", 0)
            if n_selected == 0:
                n_selected = len(selection.get("selected", []))
        else:
            n_selected = len(selection)

        logger.info(f"Step 3: Final Selection -> {n_selected} assets")

        # Calculate Funnel
        if n_discovered > 0:
            retention = (n_selected / n_discovered) * 100
            logger.info(f"Funnel Retention: {retention:.1f}%")

        # Analyze Vetoes
        vetoes = data.get("selection", {}).get("vetoes", {})
        if not vetoes:
            vetoes = data.get("vetoes", {})

        if vetoes:
            logger.info(f"Veto Count: {len(vetoes)}")
            reasons = []
            if isinstance(vetoes, dict):
                for sym, reason_list in vetoes.items():
                    reasons.extend(reason_list)
            elif isinstance(vetoes, list):
                for v in vetoes:
                    reasons.append(v.get("reason"))

            clean_reasons = []
            for r in reasons:
                if r and "High friction" in r:
                    clean_reasons.append("High Friction (Momentum/ECI)")
                elif r and "Low Efficiency" in r:
                    clean_reasons.append("Low Efficiency (ER)")
                elif r and "Random Walk" in r:
                    clean_reasons.append("Random Walk (Hurst)")
                else:
                    clean_reasons.append(r)

            if clean_reasons:
                print(pd.Series(clean_reasons).value_counts().to_markdown())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", help="Run ID to audit (optional)", default=None)
    args = parser.parse_args()
    audit_selection(args.run_id)
