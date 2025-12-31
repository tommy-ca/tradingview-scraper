import argparse
import logging
import os
import subprocess
import sys
from datetime import datetime
from typing import List, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("production_pipeline")


class ProductionPipeline:
    def __init__(self, profile: str = "production", manifest: str = "configs/manifest.json"):
        self.profile = profile
        self.manifest = manifest
        self.run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
        os.environ["TV_PROFILE"] = profile
        os.environ["TV_MANIFEST_PATH"] = manifest
        os.environ["TV_RUN_ID"] = self.run_id

    def run_step(self, name: str, command: List[str], env: Optional[dict] = None):
        logger.info(f">>> Step: {name}")
        full_env = os.environ.copy()
        if env:
            full_env.update(env)

        try:
            result = subprocess.run(command, env=full_env, check=True)
            return result.returncode == 0
        except subprocess.CalledProcessError as e:
            logger.error(f"Step '{name}' failed with return code {e.returncode}")
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
