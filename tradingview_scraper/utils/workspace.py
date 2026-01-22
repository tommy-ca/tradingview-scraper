import os
import shutil
import logging
from pathlib import Path
from typing import Optional, List

logger = logging.getLogger(__name__)


class WorkspaceManager:
    """
    Handles the creation and management of isolated workspaces for pipeline runs.
    Supports symlinking shared resources and creating immutable snapshots.
    """

    def __init__(self, run_id: str, data_root: Path = Path("data")):
        self.run_id = run_id
        self.data_root = data_root.resolve()

        # Standard subdirectories
        self.lakehouse_dir = self.data_root / "lakehouse"
        self.export_dir = self.data_root / "export"
        self.artifacts_dir = self.data_root / "artifacts"
        self.summaries_dir = self.artifacts_dir / "summaries"
        self.runs_dir = self.summaries_dir / "runs"
        self.run_dir = self.runs_dir / self.run_id
        self.snapshots_dir = self.data_root / "snapshots"

    def setup_worker_workspace(self, worker_cwd: Path, host_cwd: Path):
        """
        Sets up the worker's working directory with necessary symlinks to shared host data.
        """
        worker_cwd.mkdir(parents=True, exist_ok=True)

        # 1. Create base data directory in worker
        worker_data = worker_cwd / "data"
        worker_data.mkdir(parents=True, exist_ok=True)

        def link_shared(name: str):
            host_path = host_cwd / "data" / name
            worker_path = worker_data / name

            if not host_path.exists():
                logger.warning(f"Shared host path missing: {host_path}")
                return

            if worker_path.exists():
                if worker_path.is_symlink():
                    return
                # If it's a directory but empty, we can link over it
                if worker_path.is_dir() and not any(worker_path.iterdir()):
                    worker_path.rmdir()
                else:
                    logger.warning(f"Worker path {worker_path} already exists and is not empty. Skipping link.")
                    return

            os.symlink(host_path, worker_path)
            logger.info(f"🔗 Linked shared {name}: {worker_path} -> {host_path}")

        # Link shared inputs
        link_shared("lakehouse")
        link_shared("export")

        # Link .venv for uv execution parity
        host_venv = host_cwd / ".venv"
        worker_venv = worker_cwd / ".venv"
        if host_venv.exists() and not worker_venv.exists():
            os.symlink(host_venv, worker_venv)
            logger.info(f"🔗 Linked .venv: {worker_venv} -> {host_venv}")

        # Ensure local output directories exist
        (worker_data / "artifacts").mkdir(parents=True, exist_ok=True)
        (worker_data / "logs").mkdir(parents=True, exist_ok=True)

    def create_golden_snapshot(self) -> Path:
        """
        Creates an immutable snapshot of the current foundation data for this run.
        Copies small metadata files and hard-links large data blobs.
        """
        snapshot_path = self.snapshots_dir / self.run_id
        snapshot_path.mkdir(parents=True, exist_ok=True)

        logger.info(f"Creating Golden Snapshot for {self.run_id} at {snapshot_path}")

        # 1. Snapshot Metadata (Copy)
        metadata_files = [
            "portfolio_candidates.json",
            "portfolio_candidates_raw.json",
            "foundation_health.json",
            "symbols.parquet",  # Small enough to copy? Maybe hardlink if large.
        ]

        for f in metadata_files:
            src = self.lakehouse_dir / f
            if src.exists():
                shutil.copy2(src, snapshot_path / f)

        # 2. Snapshot Data Blobs (Hardlink)
        # We only snapshot files relevant to the current run to save space/inodes.
        # For now, let's hardlink everything in the root lakehouse.
        for item in self.lakehouse_dir.iterdir():
            if item.name in metadata_files:
                continue
            if item.is_file() and item.suffix == ".parquet":
                target = snapshot_path / item.name
                if not target.exists():
                    try:
                        os.link(item, target)
                    except OSError:
                        # Fallback to symlink if hardlinks are not supported or cross-device
                        os.symlink(item, target)
            elif item.is_dir() and item.name == "features":
                # Deep copy or link features? Features are large.
                # For now, symlink the whole features tree.
                target = snapshot_path / item.name
                if not target.exists():
                    os.symlink(item, target)

        return snapshot_path

    def resolve_run_input(self, filename: str) -> Path:
        """Resolves an input file, prioritizing the run directory, then snapshot, then lakehouse."""
        # 1. Run Directory (Latest local modifications)
        run_file = self.run_dir / "data" / filename
        if run_file.exists():
            return run_file

        # 2. Snapshot (Point-in-time foundation)
        snapshot_file = self.snapshots_dir / self.run_id / filename
        if snapshot_file.exists():
            return snapshot_file

        # 3. Global Lakehouse (Fallback)
        return self.lakehouse_dir / filename
