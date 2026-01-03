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
        self.console = Console()

        # Initialize environment BEFORE loading settings
        os.environ["TV_PROFILE"] = profile
        os.environ["TV_MANIFEST_PATH"] = str(self.manifest_path)
        os.environ["TV_RUN_ID"] = self.run_id
        os.environ["TV_EXPORT_RUN_ID"] = self.run_id

        # Promote common override env vars to TV_ prefixed settings vars
        self._promote_env_overrides()

        # Clear settings cache to ensure it picks up the new env vars

        get_settings.cache_clear()
        self.settings = get_settings()

        # Setup Audit Ledger
        self.run_dir = self.settings.prepare_summaries_run_dir()
        self.log_dir = self.run_dir / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.ledger = None
        if self.settings.features.feat_audit_ledger:
            self.ledger = AuditLedger(self.run_dir)

            # Record Genesis
            manifest_hash = self._get_file_hash(self.manifest_path)
            self.ledger.record_genesis(self.run_id, self.profile, manifest_hash)

    def _promote_env_overrides(self) -> None:
        """Map non-prefixed override env vars to TV_ prefixed settings vars."""
        overrides = {
            "LOOKBACK": "TV_LOOKBACK_DAYS",
            "PORTFOLIO_LOOKBACK_DAYS": "TV_PORTFOLIO_LOOKBACK_DAYS",
            "BACKTEST_TRAIN": "TV_TRAIN_WINDOW",
            "BACKTEST_TEST": "TV_TEST_WINDOW",
            "BACKTEST_STEP": "TV_STEP_SIZE",
            "BACKTEST_SIMULATOR": "TV_BACKTEST_SIMULATOR",
            "BACKTEST_SIMULATORS": "TV_BACKTEST_SIMULATORS",
            "RAW_POOL_UNIVERSE": "TV_RAW_POOL_UNIVERSE",
        }
        for src, dst in overrides.items():
            val = os.getenv(src)
            if val and not os.getenv(dst):
                os.environ[dst] = val

    def _get_file_hash(self, path: Path) -> str:
        if not path.exists():
            return "0" * 64
        with open(path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()

    def run_step(
        self,
        name: str,
        command: List[str],
        step_num: int = 0,
        env: Optional[Dict[str, str]] = None,
        validate_fn: Optional[Callable[[], Any]] = None,
        progress: Optional[Progress] = None,
        task_id: Optional[Any] = None,
    ):
        if progress:
            progress.console.print(f"[bold blue]>>> Step {step_num if step_num else ''}: {name}[/]")
        else:
            logger.info(f">>> Step {step_num if step_num else ''}: {name}")

        # Setup step-specific log file
        safe_name = name.lower().replace(" ", "_").replace("&", "and")
        log_file_path = self.log_dir / f"{step_num:02d}_{safe_name}.log" if step_num else self.log_dir / f"{safe_name}.log"

        # Log Intent
        if self.ledger:
            self.ledger.record_intent(step=name.lower(), params={"cmd": " ".join(command), "log_file": str(log_file_path)}, input_hashes={})

        full_env = os.environ.copy()
        if env:
            full_env.update(env)

        try:
            # Use Popen to capture output incrementally
            process = subprocess.Popen(
                command,
                env=full_env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,  # Merge stderr into stdout for simple logging
                text=True,
                bufsize=1,  # Line buffered
            )

            stdout_lines = []

            with open(log_file_path, "w", encoding="utf-8") as log_file:
                # Read stdout incrementally
                if process.stdout:
                    for line in iter(process.stdout.readline, ""):
                        # Write to log file
                        log_file.write(line)
                        log_file.flush()

                        clean_line = line.strip()
                        if clean_line:
                            stdout_lines.append(clean_line)
                            if progress and task_id is not None:
                                # Update progress bar with current activity
                                display_line = clean_line[:80] + "..." if len(clean_line) > 80 else clean_line
                                progress.update(task_id, description=f"[cyan]{name}[/] [dim]({display_line})[/]")

                                # Optional: Parse progress markers like [5/100] or 5% or Processing 5/100
                                import re

                                match = re.search(r"(\d+)/(\d+)", clean_line)
                                if match:
                                    current, total = map(int, match.groups())
                                    progress.update(task_id, completed=current, total=total)
                                elif "%" in clean_line:
                                    pct_match = re.search(r"(\d+)%", clean_line)
                                    if pct_match:
                                        progress.update(task_id, completed=int(pct_match.group(1)), total=100)

            process.wait()

            if process.returncode != 0:
                raise subprocess.CalledProcessError(process.returncode, command, output="\n".join(stdout_lines))

            # Post-run validation and metric extraction
            metrics: Dict[str, Any] = {"stdout_len": len("\n".join(stdout_lines)), "log_file": str(log_file_path)}
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

    def snapshot_resolved_manifest(self):
        """Generates a fully resolved manifest snapshot for replayability."""
        import hashlib
        import subprocess

        settings = get_settings()
        resolved = settings.model_dump(exclude={"summaries_dir"})

        # Add Replay Context
        resolved["replay_context"] = {"run_id": self.run_id, "timestamp": datetime.now().isoformat(), "git_commit": "unknown", "manifest_source": str(self.manifest_path), "foundation_hashes": {}}

        # Hash Foundation Files (Index lists)
        foundation_files = ["data/index/sp500_symbols.txt", "data/index/nasdaq100_symbols.txt", "data/index/dw30_symbols.txt"]
        for f_path in foundation_files:
            p = Path(f_path)
            if p.exists():
                sha = hashlib.sha256(p.read_bytes()).hexdigest()
                resolved["replay_context"]["foundation_hashes"][f_path] = sha

        try:
            resolved["replay_context"]["git_commit"] = subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=subprocess.STDOUT).decode().strip()
        except Exception:
            pass

        snapshot_path = self.settings.run_config_dir / "resolved_manifest.json"
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        with open(snapshot_path, "w") as f:
            json.dump(resolved, f, indent=2, default=str)

        self.console.print(f"[dim]Snapshot:[/] [green]✓[/] {snapshot_path.name}")

    def execute(self, start_step: int = 1):
        self.console.print("\n[bold cyan]🚀 Starting Production Pipeline[/]")
        self.console.print(f"[dim]Profile:[/] {self.profile} | [dim]Run ID:[/] {self.run_id} | [dim]Start Step:[/] {start_step}\n")

        lightweight_lookback = os.getenv("LOOKBACK") or os.getenv("TV_LOOKBACK_DAYS") or "60"
        lightweight_batch = os.getenv("BATCH") or "5"
        high_integrity_lookback = (
            os.getenv("PORTFOLIO_LOOKBACK_DAYS")
            or os.getenv("TV_PORTFOLIO_LOOKBACK_DAYS")
            or os.getenv("LOOKBACK")
            or os.getenv("TV_LOOKBACK_DAYS")
            or str(self.settings.resolve_portfolio_lookback_days())
        )

        make_base = ["make", f"PROFILE={self.profile}", f"MANIFEST={self.manifest_path}"]

        all_steps: List[Tuple[str, List[str], Optional[Callable[[], Any]]]] = [
            ("Cleanup", [*make_base, "clean-run"], None),
            ("Environment Check", [*make_base, "env-check"], None),
            ("Discovery", [*make_base, "scan-run"], self.validate_discovery),
            ("Aggregation", [*make_base, "data-prep-raw"], None),
            ("Lightweight Prep", [*make_base, "data-fetch", f"LOOKBACK={lightweight_lookback}", f"BATCH={lightweight_batch}"], None),
            ("Natural Selection", [*make_base, "port-select"], self.validate_selection),
            ("Enrichment", [*make_base, "meta-refresh"], None),
            ("High-Integrity Preparation", [*make_base, "data-fetch", f"LOOKBACK={high_integrity_lookback}"], None),
            ("Health Audit", [*make_base, "data-audit", "STRICT_HEALTH=1"], self.validate_health),
            ("Factor Analysis", [*make_base, "port-analyze"], None),
            ("Optimization", [*make_base, "port-optimize"], self.validate_optimization),
            ("Validation", [*make_base, "port-test"], None),
            ("Reporting", [*make_base, "port-report"], None),
            ("Gist Sync", [*make_base, "report-sync"], None),
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

            for idx, (name, cmd, val_fn) in enumerate(steps_to_run):
                # Calculate the absolute step index (start_step + current relative index)
                absolute_step = start_step + idx

                step_task = progress.add_task(f"[cyan]{name}", total=None)  # indeterminate by default
                success = self.run_step(name, cmd, step_num=absolute_step, validate_fn=val_fn, progress=progress, task_id=step_task)

                # Snapshot the manifest after Cleanup (Step 1)
                if absolute_step == 1 and success:
                    self.snapshot_resolved_manifest()

                # Integrated Recovery for Step 8 (Health Audit)
                if name == "Health Audit" and not success:
                    progress.console.print("[bold yellow]>>> Health Audit failed. Triggering Self-Healing Recovery Loop...[/]")
                    if self.ledger:
                        self.ledger.record_intent(step="recovery", params={"trigger": "health_audit_fail"}, input_hashes={})

                    # Execute Recovery
                    recovery_task = progress.add_task("[yellow]Self-Healing Recovery", total=None)
                    if self.run_step("Recovery", [*make_base, "data-repair"], step_num=absolute_step, progress=progress, task_id=recovery_task):
                        progress.console.print("[bold green]>>> Recovery complete. Re-auditing health...[/]")
                        # Re-run Health Audit (Hard Gate)
                        audit_retry_task = progress.add_task("[cyan]Health Audit (Post-Recovery)", total=None)
                        if not self.run_step(
                            "Health Audit (Post-Recovery)", [*make_base, "data-audit"], step_num=absolute_step, validate_fn=self.validate_health, progress=progress, task_id=audit_retry_task
                        ):
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
