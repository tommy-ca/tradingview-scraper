import argparse
import json
import logging
import os
import shutil
import sys
from datetime import datetime

from rich import box  # type: ignore
from rich.console import Console  # type: ignore
from rich.table import Table  # type: ignore

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("portfolio_state")

STATE_FILE = "data/lakehouse/portfolio_actual_state.json"
OPTIMIZED_FILE = "data/lakehouse/portfolio_optimized_v2.json"


def _load_optimized_data() -> dict:
    if not os.path.exists(OPTIMIZED_FILE):
        raise FileNotFoundError(f"Optimized portfolio file missing: {OPTIMIZED_FILE}")

    with open(OPTIMIZED_FILE, "r") as f:
        optimized_data = json.load(f)

    if not isinstance(optimized_data, dict) or "profiles" not in optimized_data:
        raise ValueError(f"Optimized portfolio file missing 'profiles': {OPTIMIZED_FILE}")

    return optimized_data


def _write_state_snapshot(profiles: dict, *, backup: bool = True) -> str:
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)

    if backup and os.path.exists(STATE_FILE):
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"{STATE_FILE}.bak_{ts}"
        shutil.copy2(STATE_FILE, backup_path)

    tmp_path = f"{STATE_FILE}.tmp"
    with open(tmp_path, "w") as f:
        json.dump(profiles, f, indent=2)
    os.replace(tmp_path, STATE_FILE)
    return STATE_FILE


def accept_state(*, backup: bool = True) -> int:
    try:
        optimized_data = _load_optimized_data()
        profiles = optimized_data.get("profiles")
        if not isinstance(profiles, dict):
            raise ValueError("Optimized portfolio file has invalid 'profiles' payload")

        _write_state_snapshot(profiles, backup=backup)
        logger.info("Accepted current optimized portfolio as actual state snapshot.")
        return 0
    except Exception as e:
        logger.error(f"Failed to accept state: {e}")
        return 1


def track_drift():
    console = Console()
    try:
        optimized_data = _load_optimized_data()
    except Exception as e:
        logger.error(str(e))
        return

    # If state file doesn't exist, initialize it with current optimal (Snapshot)
    if not os.path.exists(STATE_FILE):
        logger.info("Initializing portfolio state snapshot...")
        profiles = optimized_data.get("profiles")
        if isinstance(profiles, dict):
            _write_state_snapshot(profiles, backup=False)
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
    parser = argparse.ArgumentParser(description="Portfolio drift monitor and state snapshotter")
    parser.add_argument("--accept", action="store_true", help="Overwrite the last implemented state with the current optimized portfolio (use after implementation)")
    parser.add_argument("--no-backup", action="store_true", help="Disable backup when overwriting an existing state file")
    args = parser.parse_args()

    if args.accept:
        sys.exit(accept_state(backup=not args.no_backup))

    track_drift()
