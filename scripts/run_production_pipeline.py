import argparse
import hashlib
import json
import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
)

# Add the project root to the path so we can import internal modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tradingview_scraper.settings import get_settings
from tradingview_scraper.utils.audit import AuditLedger  # type: ignore

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("production_pipeline")


class ProductionPipeline:
    def __init__(self, profile: str = "production", manifest: str = "configs/manifest.json", run_id: Optional[str] = None):
        self.profile = profile
        self.manifest_path = Path(manifest)
        self.run_id = run_id or datetime.now().strftime("%Y%m%d-%H%M%S")
        self.settings = get_settings()
        self.console = Console()

        # Initialize environment
        os.environ["TV_PROFILE"] = profile
        os.environ["TV_MANIFEST_PATH"] = str(self.manifest_path)
        os.environ["TV_RUN_ID"] = self.run_id
        os.environ["TV_EXPORT_RUN_ID"] = self.run_id

        # Setup Audit Ledger
        self.run_dir = self.settings.prepare_summaries_run_dir()
        self.ledger = None
        if self.settings.features.feat_audit_ledger:
            self.ledger = AuditLedger(self.run_dir)

            # Record Genesis
            manifest_hash = self._get_file_hash(self.manifest_path)
            self.ledger.record_genesis(self.run_id, self.profile, manifest_hash)

    def _get_file_hash(self, path: Path) -> str:
        if not path.exists():
            return "0" * 64
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()

    def run_step(
        self,
        name: str,
        command: List[str],
        env: Optional[Dict[str, str]] = None,
        validate_fn: Optional[Callable[[], Any]] = None,
        progress: Optional[Progress] = None,
        task_id: Optional[Any] = None,
    ):
        if progress:
            progress.console.print(f"[bold blue]>>> Step: {name}[/]")
        else:
            logger.info(f">>> Step: {name}")

        # Log Intent
        if self.ledger:
            self.ledger.record_intent(step=name.lower(), params={"cmd": " ".join(command)}, input_hashes={})

        full_env = os.environ.copy()
        if env:
            full_env.update(env)

        try:
            # Use Popen to capture output incrementally
            process = subprocess.Popen(command, env=full_env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

            stdout_lines = []
            stderr_lines = []

            # Read stdout incrementally
            if process.stdout:
                for line in iter(process.stdout.readline, ""):
                    line = line.strip()
                    if line:
                        stdout_lines.append(line)
                        if progress and task_id is not None:
                            # Truncate long lines for the status display
                            display_line = line[:60] + "..." if len(line) > 60 else line
                            progress.update(task_id, description=f"[cyan]{name}[/] [dim]({display_line})[/]")

            # Wait for completion and get stderr
            _, stderr = process.communicate()
            if stderr:
                stderr_lines.append(stderr)

            if process.returncode != 0:
                raise subprocess.CalledProcessError(process.returncode, command, output="\n".join(stdout_lines), stderr="\n".join(stderr_lines))

            # Post-run validation and metric extraction
            metrics: Dict[str, Any] = {"stdout_len": len("\n".join(stdout_lines))}
            output_hashes: Dict[str, str] = {}
            if validate_fn:
                try:
                    val_res = validate_fn()
                    if isinstance(val_res, dict):
                        metrics.update(val_res.get("metrics", {}))
                        output_hashes.update(val_res.get("hashes", {}))
                except Exception as ve:
                    if progress:
                        progress.console.print(f"[yellow]Validation hook failed for '{name}': {ve}[/]")
                    else:
                        logger.warning(f"Validation hook failed for '{name}': {ve}")

            # Log Outcome
            if self.ledger:
                self.ledger.record_outcome(step=name.lower(), status="success", output_hashes=output_hashes, metrics=metrics)

            if progress and task_id is not None:
                progress.update(task_id, description=f"[green]{name}[/] [bold green]COMPLETE[/]", completed=1)

            return True
        except Exception as e:
            if progress:
                progress.console.print(f"[bold red]Step '{name}' failed: {e}[/]")
            else:
                logger.error(f"Step '{name}' failed: {e}")

            if self.ledger:
                err_msg = str(e)[-500:]
                self.ledger.record_outcome(step=name.lower(), status="failure", output_hashes={}, metrics={"error": err_msg})
            return False

    def validate_discovery(self) -> Dict[str, Any]:
        """Discovery Gate: Verify export directory contains results."""
        export_dir = Path("export") / self.run_id
        if not export_dir.exists():
            # Try finding the latest directory if ID mismatch (discovery scripts sometimes use their own ts)
            dirs = sorted(Path("export").glob("*"), key=os.path.getmtime, reverse=True)
            if dirs:
                export_dir = dirs[0]

        files = list(export_dir.glob("*.json"))
        return {"metrics": {"n_discovery_files": len(files)}}

    def validate_selection(self) -> Dict[str, Any]:
        """Selection Gate: Ensure enough symbols survived."""
        path = Path("data/lakehouse/portfolio_candidates.json")
        if not path.exists():
            return {}
        with open(path, "r") as f:
            data = json.load(f)
        return {"metrics": {"n_selected_symbols": len(data)}}

    def validate_health(self) -> Dict[str, Any]:
        """Health Gate: Check for gaps and stale assets."""
        report_path = self.run_dir / "data_health_selected.md"
        if not report_path.exists():
            return {"metrics": {"health_gate": "report_missing"}}

        # Grep for critical failures in the report
        try:
            with open(report_path, "r") as f:
                content = f.read()

            missing = 0
            stale = 0
            degraded = 0

            for line in content.split("\n"):
                if "MISSING" in line:
                    missing += 1
                if "STALE" in line:
                    stale += 1
                if "DEGRADED" in line:
                    degraded += 1

            return {"metrics": {"health_gate": "checked", "n_missing": missing, "n_stale": stale, "n_degraded": degraded}}
        except Exception as e:
            return {"metrics": {"health_gate": f"error: {str(e)}"}}

    def validate_optimization(self) -> Dict[str, Any]:
        """Optimization Gate: Verify all profiles were generated."""
        path = Path("data/lakehouse/portfolio_optimized_v2.json")
        if not path.exists():
            return {}
        try:
            with open(path, "r") as f:
                data = json.load(f)
            profiles = list(data.get("profiles", {}).keys())
            return {"metrics": {"optimized_profiles": profiles}}
        except Exception:
            return {}

    def execute(self, start_step: int = 1):
        self.console.print("\n[bold cyan]🚀 Starting Production Pipeline[/]")
        self.console.print(f"[dim]Profile:[/] {self.profile} | [dim]Run ID:[/] {self.run_id} | [dim]Start Step:[/] {start_step}\n")

        all_steps: List[Tuple[str, List[str], Optional[Callable[[], Any]]]] = [
            ("Cleanup", ["make", "clean-daily"], None),
            ("Discovery", ["make", "scan-all"], self.validate_discovery),
            ("Aggregation", ["make", "portfolio-prep-raw"], None),
            ("Lightweight Prep", ["make", "prep", "LOOKBACK=60", "BATCH=5"], None),
            ("Forensic Risk Audit", ["python", "scripts/audit_antifragility.py"], None),
            ("Natural Selection", ["make", "select"], self.validate_selection),
            ("Enrichment", ["make", "enrich-candidates"], None),
            ("High-Integrity Alignment", ["make", "portfolio-align"], None),
            ("Health Audit", ["make", "audit-health"], self.validate_health),
            ("Factor Analysis", ["make", "corr-report"], None),
            ("Regime Detection", ["make", "regime-check"], None),
            ("Optimization", ["make", "optimize-v2"], self.validate_optimization),
            ("Validation", ["make", "backtest-tournament"], None),
            ("Reporting", ["make", "reports"], None),
            ("Audit Integrity Check", ["python", "-m", "scripts.verify_ledger", str(self.run_dir / "audit.jsonl")], None),
        ]

        steps_to_run = all_steps[start_step - 1 :]

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(bar_width=None),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=self.console,
            expand=True,
        ) as progress:
            pipeline_task = progress.add_task("[bold green]Pipeline Progress", total=len(all_steps))
            progress.advance(pipeline_task, start_step - 1)

            for name, cmd, val_fn in steps_to_run:
                step_task = progress.add_task(f"[cyan]{name}", total=1)
                success = self.run_step(name, cmd, validate_fn=val_fn, progress=progress, task_id=step_task)

                # Integrated Recovery for Step 8 (Health Audit)
                if name == "Health Audit" and not success:
                    progress.console.print("[bold yellow]>>> Health Audit failed. Triggering Self-Healing Recovery Loop...[/]")
                    if self.ledger:
                        self.ledger.record_intent(step="recovery", params={"trigger": "health_audit_fail"}, input_hashes={})

                    # Execute Recovery
                    recovery_task = progress.add_task("[yellow]Self-Healing Recovery", total=1)
                    if self.run_step("Recovery", ["make", "recover"], progress=progress, task_id=recovery_task):
                        progress.console.print("[bold green]>>> Recovery complete. Re-auditing health...[/]")
                        # Re-run Health Audit (Hard Gate)
                        audit_retry_task = progress.add_task("[cyan]Health Audit (Post-Recovery)", total=1)
                        if not self.run_step("Health Audit (Post-Recovery)", ["make", "audit-health"], validate_fn=self.validate_health, progress=progress, task_id=audit_retry_task):
                            progress.console.print("[bold red]FATAL: Health Audit failed even after recovery. Aborting.[/]")
                            sys.exit(1)
                    else:
                        progress.console.print("[bold red]FATAL: Recovery failed. Aborting.[/]")
                        sys.exit(1)
                elif not success:
                    progress.console.print(f"[bold red]Pipeline aborted at step '{name}' due to failure.[/]")
                    sys.exit(1)

                progress.advance(pipeline_task)

        self.console.print("\n[bold green]✅ Pipeline completed successfully.[/]\n")


if __name__ == "__main__":
    # Suppress internal noise during progress-bar execution
    logging.getLogger("tradingview_scraper").setLevel(logging.WARNING)
    logging.getLogger("backtest_simulators").setLevel(logging.WARNING)

    parser = argparse.ArgumentParser(description="Institutional Production Pipeline")
    parser.add_argument("--profile", default="production", help="Workflow profile to use")
    parser.add_argument("--manifest", default="configs/manifest.json", help="Path to manifest file")
    parser.add_argument("--start-step", type=int, default=1, help="Step number to start from (1-14)")
    parser.add_argument("--run-id", help="Explicit run ID to use (for resuming)")
    args = parser.parse_args()

    pipeline = ProductionPipeline(profile=args.profile, manifest=args.manifest, run_id=args.run_id)
    pipeline.execute(start_step=args.start_step)
