import json
import logging
import os

from rich import box  # type: ignore
from rich.console import Console  # type: ignore
from rich.table import Table  # type: ignore

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("portfolio_state")

STATE_FILE = "data/lakehouse/portfolio_actual_state.json"
OPTIMIZED_FILE = "data/lakehouse/portfolio_optimized_v2.json"


def track_drift():
    console = Console()
    if not os.path.exists(OPTIMIZED_FILE):
        logger.error("Optimized portfolio file missing.")
        return

    with open(OPTIMIZED_FILE, "r") as f:
        optimized_data = json.load(f)

    # If state file doesn't exist, initialize it with current optimal (Snapshot)
    if not os.path.exists(STATE_FILE):
        logger.info("Initializing portfolio state snapshot...")
        with open(STATE_FILE, "w") as f:
            json.dump(optimized_data["profiles"], f, indent=2)
        console.print("[bold green]Portfolio state initialized.[/] Run again after future optimizations to see drift.")
        return

    with open(STATE_FILE, "r") as f:
        actual_state = json.load(f)

    console.print("\n[bold cyan]📉 Portfolio Rebalancing Drift Analysis[/]")
    console.print("[dim]Comparing current optimal vs. last implemented state.[/]\n")

    for profile_name in optimized_data["profiles"].keys():
        current_assets = {a["Symbol"]: a["Weight"] for a in optimized_data["profiles"][profile_name]["assets"]}
        last_assets = {a["Symbol"]: a["Weight"] for a in actual_state.get(profile_name, {}).get("assets", [])}

        all_symbols = sorted(set(current_assets.keys()) | set(last_assets.keys()))

        table = Table(title=f"Profile: {profile_name.replace('_', ' ').title()}", box=box.SIMPLE)
        table.add_column("Symbol", style="cyan")
        table.add_column("Last %", justify="right")
        table.add_column("Target %", justify="right", style="bold green")
        table.add_column("Drift", justify="right", style="bold magenta")
        table.add_column("Action", justify="center")

        total_drift = 0.0
        for sym in all_symbols:
            w_last = float(last_assets.get(sym, 0.0))
            w_target = float(current_assets.get(sym, 0.0))
            drift = w_target - w_last
            total_drift += abs(drift)

            if abs(drift) < 0.001:
                continue

            action = "BUY" if drift > 0 else "SELL"
            table.add_row(str(sym), f"{w_last:.2%}", f"{w_target:.2%}", f"{drift:+.2%}", f"[bold {'green' if drift > 0 else 'red'}]{action}[/]")

        console.print(table)
        console.print(f"[dim]Total Turnover Required: {total_drift / 2:.2%}[/]\n")


if __name__ == "__main__":
    track_drift()
