import json
from datetime import datetime


def generate_markdown_report(data_path: str, output_path: str):
    with open(data_path, "r") as f:
        data = json.load(f)

    profiles = data.get("profiles", {})

    md = []
    md.append("# 📊 Clustered Portfolio Analysis Report")
    md.append(f"**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    md.append("\n**See Also:** [Deeper Cluster Analysis](./cluster_analysis.md)")
    md.append("\n---")

    for profile_name, profile_data in profiles.items():
        pretty_name = profile_name.replace("_", " ").title()
        md.append(f"\n## 📈 {pretty_name} Profile")

        # Cluster Summary Table
        md.append("### 🧩 Risk Bucket Allocation (Clusters)")
        md.append("| Cluster | Weight | Lead Asset | Assets | Type | Sectors |")
        md.append("| :--- | :--- | :--- | :--- | :--- | :--- |")

        for cluster in profile_data.get("clusters", []):
            weight = f"{cluster['Total_Weight']:.2%}"
            lead = f"`{cluster['Lead_Asset']}`"
            count = cluster["Asset_Count"]
            risk_type = cluster.get("Type", "CORE")
            sector = cluster.get("Sectors", "N/A")
            if isinstance(sector, list):
                sector = ", ".join(sector)

            md.append(f"| {cluster['Cluster_Label']} | **{weight}** | {lead} | {count} | {risk_type} | {sector} |")

        # Top Assets Table
        md.append("\n### 💎 Top Individual Allocations")
        md.append("| Symbol | Description | Weight | Direction | Market |")
        md.append("| :--- | :--- | :--- | :--- | :--- |")

        # Sort by weight and take top 15
        assets = sorted(profile_data.get("assets", []), key=lambda x: x["Weight"], reverse=True)
        for asset in assets[:15]:
            weight = f"{asset['Weight']:.2%}"
            direction = f"**{asset['Direction']}**"
            desc = asset.get("Description", "N/A")
            if len(desc) > 40:
                desc = desc[:37] + "..."

            md.append(f"| `{asset['Symbol']}` | {desc} | {weight} | {direction} | {asset['Market']} |")

        md.append("\n---")

    with open(output_path, "w") as f:
        f.write("\n".join(md))

    print(f"✅ Prettified report generated at: {output_path}")


if __name__ == "__main__":
    generate_markdown_report("data/lakehouse/portfolio_optimized_v2.json", "summaries/portfolio_report.md")
