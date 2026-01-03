import json
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd


def generate_selection_report(
    audit_path: str = "data/lakehouse/selection_audit.json",
    output_path: str = "selection_audit.md",
    audit_data: Optional[Dict[str, Any]] = None,
):
    """
    Generates a markdown report summarizing the universe selection process.
    """
    path = Path(audit_path)
    if not path.exists():
        print(f"Selection audit not found at {path}")
        return

    try:
        with open(path, "r") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Failed to load selection audit: {e}")
        return

    md = ["# Universe Selection Report", f"Source: `{audit_path}`", ""]

    # 1. Selection Metadata
    md.append("## 1. Selection Context")
    md.append(f"- **Selection Mode**: {data.get('selection_mode', 'N/A')}")
    md.append(f"- **Lookback Days**: {data.get('lookback_days', 'N/A')}")
    md.append(f"- **Lookback Windows**: {data.get('lookbacks', [])}")
    md.append(f"- **Total Candidates**: {len(data.get('candidates', []))}")
    md.append(f"- **Selected Winners**: {len(data.get('winners', []))}")
    md.append("")

    # 2. Winners Table
    if "winners" in data:
        md.append("## 2. Selected Winners")
        winners = data["winners"]
        if winners:
            # Try to enrich with metadata if available in 'candidates' list
            candidate_map = {c["symbol"]: c for c in data.get("candidates", []) if isinstance(c, dict) and "symbol" in c}

            rows = []
            for sym in winners:
                if not isinstance(sym, str):
                    continue
                c_info = candidate_map.get(sym, {})
                rows.append(
                    {
                        "Symbol": sym,
                        "Sector": c_info.get("sector", "N/A"),
                        "Asset Class": c_info.get("asset_class", "N/A"),
                        "Direction": c_info.get("direction", "LONG"),
                    }
                )

            if rows:
                df = pd.DataFrame(rows)
                md.append(df.to_markdown(index=False))
        else:
            md.append("No winners selected.")
        md.append("")

    # 3. Vetoed Assets
    if "vetoes" in data:
        md.append("## 3. Selection Vetoes")
        vetoes = data["vetoes"]
        if vetoes:
            md.append(f"Total Vetoes: {len(vetoes)}")
            # If vetoes is a dict of symbol -> reason
            if isinstance(vetoes, dict):
                v_rows = [{"Symbol": s, "Reason": r} for s, r in vetoes.items()]
                md.append(pd.DataFrame(v_rows).to_markdown(index=False))
            else:
                for v in vetoes:
                    md.append(f"- {str(v)}")
        else:
            md.append("No assets were vetoed.")
        md.append("")

    # Write output
    try:
        out_p = Path(output_path)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        with open(out_p, "w") as f:
            f.write("\n".join(md))
        print(f"Selection report saved to {output_path}")
    except Exception as e:
        print(f"Failed to write selection report: {e}")


if __name__ == "__main__":
    # For standalone testing
    generate_selection_report()
