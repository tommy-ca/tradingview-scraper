import argparse
import datetime
import logging
import os
import subprocess

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("v361_certification")


def run_backtest(selection_mode, profiles, engines, simulator, run_id_prefix):
    run_id = f"{run_id_prefix}_{selection_mode}"
    logger.info(f"==> Launching Certification: Selection={selection_mode} (Run ID: {run_id})")

    # Institutional standard 60/20/20 config
    cmd = [
        "uv",
        "run",
        "scripts/backtest_engine.py",
        "--train-window",
        "60",
        "--test-window",
        "20",
        "--step-size",
        "20",
        "--selection-mode",
        selection_mode,
        "--profiles",
        ",".join(profiles),
        "--engines",
        ",".join(engines),
        "--simulators",
        simulator,
    ]

    env = os.environ.copy()
    env["TV_RUN_ID"] = run_id
    env["TV_FEATURES__FEAT_AUDIT_LEDGER"] = "1"
    env["TV_FEATURES__FEAT_MARKET_NEUTRAL"] = "1"
    env["TV_FEATURES__FEAT_DYNAMIC_DIRECTION"] = "1"
    env["TV_FEATURES__FEAT_PREDICTABILITY_VETOES"] = "1"

    try:
        subprocess.run(cmd, env=env, check=True, capture_output=True)
        return run_id
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed {run_id}: {e.stderr.decode() if e.stderr else str(e)}")
        return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id-prefix", default=f"cert_v361_{datetime.datetime.now().strftime('%m%d_%H%M')}")
    args = parser.parse_args()

    # The Exhaustive Matrix (Selection x Profile x Engine)
    selection_modes = ["v3.4", "v4", "baseline"]
    profiles = ["max_sharpe", "hrp", "min_variance", "risk_parity", "market_neutral"]
    engines = ["skfolio", "riskfolio", "custom"]
    simulator = "cvxportfolio"

    run_ids = {}
    for mode in selection_modes:
        rid = run_backtest(mode, profiles, engines, simulator, args.run_id_prefix)
        if rid:
            run_ids[mode] = rid

    # Automated Report Trigger
    logger.info(">>> Tournament Complete. Generating Institutional Forensic Matrix...")
    for mode, rid in run_ids.items():
        logger.info(f"Auditing {rid}...")
        subprocess.run(["uv", "run", "scripts/production/stable_institutional_audit.py", "--run-id", rid])
        subprocess.run(["uv", "run", "scripts/production/comprehensive_audit_v4.py", rid])

    logger.info("Full System Certification v3.6.1 Complete.")


if __name__ == "__main__":
    main()
