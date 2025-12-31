import argparse
import hashlib
import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional

# Add the project root to the path so we can import internal modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tradingview_scraper.settings import get_settings
from tradingview_scraper.utils.audit import AuditLedger  # type: ignore

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("production_pipeline")


class ProductionPipeline:
    def __init__(self, profile: str = "production", manifest: str = "configs/manifest.json"):
        self.profile = profile
        self.manifest_path = Path(manifest)
        self.run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
        self.settings = get_settings()

        # Initialize environment
        os.environ["TV_PROFILE"] = profile
        os.environ["TV_MANIFEST_PATH"] = str(self.manifest_path)
        os.environ["TV_RUN_ID"] = self.run_id

        # Setup Audit Ledger
        self.run_dir = self.settings.prepare_summaries_run_dir()
        self.ledger = AuditLedger(self.run_dir)

        # Record Genesis
        manifest_hash = self._get_file_hash(self.manifest_path)
        self.ledger.record_genesis(self.run_id, self.profile, manifest_hash)

    def _get_file_hash(self, path: Path) -> str:
        if not path.exists():
            return "0" * 64
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()

    def run_step(self, name: str, command: List[str], env: Optional[dict] = None):
        logger.info(f">>> Step: {name}")

        # Log Intent
        self.ledger.record_intent(step=name.lower(), params={"cmd": " ".join(command)}, input_hashes={})

        full_env = os.environ.copy()
        if env:
            full_env.update(env)

        try:
            result = subprocess.run(command, env=full_env, check=True, capture_output=True, text=True)
            # Log Outcome
            self.ledger.record_outcome(step=name.lower(), status="success", output_hashes={}, metrics={"stdout_len": len(result.stdout)})
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Step '{name}' failed with return code {e.returncode}")
            self.ledger.record_outcome(step=name.lower(), status="failure", output_hashes={}, metrics={"error": e.stderr[-500:]})
            return False

    def execute(self):
        logger.info(f"Starting Production Pipeline (Profile: {self.profile}, Run ID: {self.run_id})")

        steps = [
            ("Cleanup", ["make", "clean-daily"]),
            ("Discovery", ["make", "scan-all"]),
            ("Aggregation", ["make", "portfolio-prep-raw"]),
            ("Natural Selection", ["make", "portfolio-prune"]),
            ("High-Integrity Alignment", ["make", "portfolio-align"]),
            ("Health Audit", ["make", "audit-health"]),
            ("Factor Analysis", ["make", "portfolio-analyze"]),
            ("Optimization & Finalize", ["make", "portfolio-finalize"]),
        ]

        for name, cmd in steps:
            if not self.run_step(name, cmd):
                logger.error("Pipeline aborted due to step failure.")
                sys.exit(1)

        logger.info("Pipeline completed successfully.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Institutional Production Pipeline")
    parser.add_argument("--profile", default="production", help="Workflow profile to use")
    parser.add_argument("--manifest", default="configs/manifest.json", help="Path to manifest file")
    args = parser.parse_args()

    pipeline = ProductionPipeline(profile=args.profile, manifest=args.manifest)
    pipeline.execute()
