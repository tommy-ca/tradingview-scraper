from __future__ import annotations

import json
import logging
import os
import re
import sys
from contextvars import ContextVar, Token
from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Any, ClassVar, Optional

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

logger = logging.getLogger(__name__)


class SelectionRanking(BaseModel):
    """Configuration for selection sorting logic."""

    method: str = "alpha_score"
    direction: str = "descending"  # "ascending" or "descending"


class FeatureFlags(BaseModel):
    """Gradual rollout toggles for 2026 Quantitative features."""

    feat_partial_rebalance: bool = False
    feat_turnover_penalty: bool = False
    feat_xs_momentum: bool = False
    feat_spectral_regimes: bool = False
    feat_decay_audit: bool = False
    feat_audit_ledger: bool = False
    feat_pit_fidelity: bool = False
    feat_rebalance_mode: str = "window"  # "daily" or "window"
    feat_rebalance_tolerance: bool = False
    rebalance_drift_limit: float = 0.05
    feat_short_costs: bool = False
    short_borrow_cost: float = 0.02  # 2% p.a.
    feat_dynamic_selection: bool = False
    feat_regime_survival: bool = False
    feat_predictability_vetoes: bool = False
    feat_efficiency_scoring: bool = False
    feat_selection_logmps: bool = False
    feat_directional_returns: bool = False
    feat_dynamic_direction: bool = False
    feat_short_direction: bool = True
    feat_market_neutral: bool = False
    feat_directional_sign_test_gate: bool = False
    feat_directional_sign_test_gate_atomic: bool = False
    feat_use_tv_ratings: bool = True  # New Flag: Use retrieved TV ratings if available (default True)

    # Risk Budgeting (Prop-style pacing)
    feat_daily_risk_budget_slices: bool = False
    feature_lookback: int = 120
    selection_mode: str = "v4"

    # Custom MPS Weight Overrides (Map[str, float])
    # Allows profiles to boost specific signals (e.g. recommend_ma) over generic momentum
    mps_weights_override: dict[str, float] = {}

    # Signal Dominance (New)
    dominant_signal: str | None = None
    dominant_signal_weight: float = 3.0

    # Predictability Thresholds
    entropy_max_threshold: float = 0.9
    efficiency_min_threshold: float = 0.1
    hurst_random_walk_min: float = 0.45
    hurst_random_walk_max: float = 0.55
    eci_hurdle: float = 0.0

    # Numerical Stability & Hardening
    kappa_shrinkage_threshold: float = 5000.0
    default_shrinkage_intensity: float = 0.01
    adaptive_fallback_profile: str = "erc"

    # Forensic Analysis Defaults
    min_col_frac: float = 0.1
    use_robust_correlation: bool = True

    # HPO Optimized Weights (Log-MPS 3.2)
    # Global Robust: Optimized across all 2025 regimes (Mean Alpha / Std Alpha)
    weights_global: dict[str, float] = {
        "momentum": 1.7469,
        "stability": 0.0458,
        "liquidity": 0.2946,
        "antifragility": 0.6263,
        "survival": 1.4000,
        "efficiency": 1.5348,
        "entropy": 0.0322,
        "hurst_clean": 0.3485,
        "adx": 1.0,
        "recommend_all": 1.0,
        "recommend_ma": 1.0,
        "skew": 0.5,
        "kurtosis": 0.5,
        "cvar": 1.0,
    }
    top_n_global: int = 5

    # HPO Optimized Weights (Selection v2.1 - Additive Rank-Sum)
    # Refined via Normalization Sensitivity Audit (2026-01-02)
    weights_v2_1_global: dict[str, float] = {
        "momentum": 0.2055,
        "stability": 0.0882,
        "liquidity": 0.1697,
        "antifragility": 0.0988,
        "survival": 0.2273,
        "efficiency": 0.1027,
        "entropy": 0.0060,
        "hurst_clean": 0.1018,
    }
    # Winner: Multi-Method Normalization Protocol
    normalization_methods_v2_1: dict[str, str] = {
        "momentum": "logistic",
        "stability": "logistic",
        "liquidity": "zscore",
        "antifragility": "rank",
        "survival": "rank",
        "efficiency": "rank",
        "entropy": "zscore",
        "hurst_clean": "zscore",
    }
    clipping_sigma_v2_1: float = 3.49
    top_n_v2_1: int = 2


class ManifestSettingsSource(PydanticBaseSettingsSource):
    """Custom settings source to load from a multi-profile JSON manifest."""

    def __init__(self, settings_cls: type[BaseSettings], manifest_path: Path, profile_name: str):
        super().__init__(settings_cls)
        self.manifest_path = manifest_path
        self.profile_name = profile_name

    def get_field_value(self, field: Any, field_name: str) -> tuple[Any, str, bool]:
        # Not used for this combined source
        return None, field_name, False

    def __call__(self) -> dict[str, Any]:
        if not self.manifest_path.exists():
            return {}

        try:
            with open(self.manifest_path, "r") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError, Exception) as e:
            logger.error(f"Error loading manifest {self.manifest_path}: {e}")
            return {}

        def _merge_blocks(target: dict, source: dict):
            """Deep merge specific manifest blocks into flattened settings."""
            for section in ["data", "selection", "risk", "backtest", "tournament", "discovery", "features"]:
                if section in source:
                    if section in {"discovery", "features"} and isinstance(source[section], dict):
                        # Nested models or complex dicts
                        if section not in target:
                            target[section] = {}
                        target[section].update(source[section])
                    elif isinstance(source[section], dict):
                        # Flatten standard sections
                        for k, v in source[section].items():
                            if k == "selection_mode":
                                if "features" not in target:
                                    target["features"] = {}
                                target["features"]["selection_mode"] = v
                            else:
                                target[k] = v

            # Merge Integrations
            if "integrations" in source:
                for k, v in source["integrations"].items():
                    target[k.lower()] = v

            # Merge Execution Env
            if "execution_env" in source:
                for k, v in source["execution_env"].items():
                    target[k.lower()] = v

        flattened = {}

        # 1. Load Global Defaults (Lowest Priority in manifest)
        defaults = data.get("defaults", {})
        _merge_blocks(flattened, defaults)

        # Add root-level integrations/execution_env if they exist outside defaults
        _merge_blocks(flattened, data)

        # 2. Resolve Active Profile
        profiles = data.get("profiles", {})
        active_profile = self.profile_name or data.get("default_profile", "production")
        profile_data = profiles.get(active_profile)

        visited = {active_profile}
        while isinstance(profile_data, str):
            if profile_data in visited:
                logger.error(f"Circular alias: {' -> '.join(visited)} -> {profile_data}")
                break
            visited.add(profile_data)
            active_profile = profile_data
            profile_data = profiles.get(active_profile)

        # 3. Merge Profile Overrides (Higher Priority)
        if isinstance(profile_data, dict):
            _merge_blocks(flattened, profile_data)

        return flattened


class TradingViewScraperSettings(BaseSettings):
    """Centralized, env-configurable paths and workflow parameters."""

    model_config = SettingsConfigDict(
        env_prefix="TV_",
        env_file=(".env",),
        extra="ignore",
        case_sensitive=False,
        env_nested_delimiter="__",
    )

    # Infrastructure
    data_dir: Path = Path("data")
    artifacts_dir: Path = Path("data/artifacts")
    lakehouse_dir: Path = Path("data/lakehouse")
    logs_dir: Path = Path("data/logs")
    export_dir: Path = Path("data/export")
    configs_dir: Path = Path("configs")
    summaries_dir: Path | None = None
    manifest_path: Path = Path("configs/manifest.json")
    profile: str = Field(default_factory=lambda: os.getenv("TV_PROFILE") or "")

    # Discovery & Prep
    batch_size: int = 5
    lookback_days: int = 200
    backfill: bool = True
    gapfill: bool = True
    max_symbols: int = 200
    strict_health: bool = False
    min_days_floor: int = 0

    # Portfolio Data Prep Overrides
    portfolio_lookback_days: int | None = None
    portfolio_batch_size: int = 1
    portfolio_backfill: bool = False
    portfolio_gapfill: bool = False
    portfolio_force_sync: bool = False
    portfolio_dedupe_base: bool = False

    # Selection Logic
    top_n: int = 3
    threshold: float = 0.4
    min_momentum_score: float = 0.0
    strategy: str = "trend_following"
    cluster_lookbacks: list[int] = [60, 120, 200]
    ranking: SelectionRanking = Field(default_factory=SelectionRanking)
    strategy_type: Optional[str] = None  # Resolved via Manifest or Profile Inference

    # Optimization
    cluster_cap: float = 0.25
    max_clusters: int = 25

    # Backtest
    train_window: int = 252
    test_window: int = 20
    step_size: int = 20
    backtest_simulator: str = "custom"
    backtest_simulators: str = "vectorbt,cvxportfolio,custom"
    backtest_slippage: float = 0.0005  # 5 bps
    backtest_commission: float = 0.0001  # 1 bp
    backtest_cash_asset: str = "USDT"
    benchmark_symbols: list[str] = Field(default_factory=lambda: ["AMEX:SPY"])
    report_mode: str = "full"
    dynamic_universe: bool = False
    raw_pool_universe: str = "selected"

    # Risk Management (New)
    exit_rules: dict[str, float] = Field(default_factory=dict)
    timeframes: list[str] = Field(default_factory=list)
    initial_capital: float = 100000.0
    max_daily_loss_pct: float = 0.05
    max_total_loss_pct: float = 0.10
    risk_reset_tz: str = "UTC"
    risk_reset_time: str = "00:00"

    # Daily Risk Budget (10 x 0.5% slices)
    risk_budget_total_slices_per_campaign: int = 10
    risk_budget_slice_pct: float = 0.005
    risk_budget_max_entries_per_day: int = 2
    risk_budget_max_slices_per_day: int = 2
    risk_budget_max_slices_per_entry: int = 2

    # Tournament
    engines: str = "custom,skfolio,riskfolio,pyportfolioopt,cvxportfolio"
    profiles: str = "min_variance,hrp,max_sharpe,barbell,benchmark,market"

    # Discovery (Structured)
    discovery: dict[str, Any] = Field(default_factory=dict)

    # Feature Flags
    features: FeatureFlags = Field(default_factory=FeatureFlags)

    # Integrations (New)
    gist_id: str = "e888e1eab0b86447c90c26e92ec4dc36"

    # Execution Env (New)
    mandatory_vars: list[str] = Field(default_factory=list)
    optional_vars: list[str] = Field(default_factory=list)

    # Runtime run_id logic
    run_id: str = Field(default_factory=lambda: os.getenv("TV_RUN_ID") or os.getenv("RUN_ID") or os.getenv("TV_EXPORT_RUN_ID") or datetime.now().strftime("%Y%m%d-%H%M%S"))

    @field_validator("run_id")
    @classmethod
    def validate_run_id(cls, v: str) -> str:
        """Ensures run_id is a valid filename and prevents path traversal."""
        if not v:
            return v

        # Strict whitelist: alphanumeric, underscore, hyphen
        if not re.match(r"^[a-zA-Z0-9_\-]+$", v):
            raise ValueError(f"Invalid run_id format: {v}. Must contain only a-z, A-Z, 0-9, _, -")

        return v

    def clone(self, **overrides: Any) -> TradingViewScraperSettings:
        """Returns a new settings object with specified overrides."""
        data = self.model_dump()
        data.update(overrides)
        return TradingViewScraperSettings(**data)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # Determine manifest path and profile before creating the source
        # We look in env vars first since Pydantic hasn't finished loading yet
        m_path = Path(os.getenv("TV_MANIFEST_PATH") or "configs/manifest.json")
        p_name = os.getenv("TV_PROFILE") or ""

        return (
            init_settings,
            dotenv_settings,
            env_settings,
            ManifestSettingsSource(settings_cls, m_path, p_name),
            file_secret_settings,
        )

    def get_discovery_config(self, scanner_type: str) -> dict[str, Any]:
        """Extracts the discovery configuration for a specific scanner type."""
        return self.discovery.get(scanner_type, {})

    def resolve_portfolio_lookback_days(self) -> int:
        if self.portfolio_lookback_days is not None:
            return int(self.portfolio_lookback_days)
        return int(self.lookback_days)

    @property
    def summaries_root_dir(self) -> Path:
        return self.summaries_dir or (self.artifacts_dir / "summaries")

    @property
    def summaries_runs_dir(self) -> Path:
        return self.summaries_root_dir / "runs"

    @property
    def summaries_run_dir(self) -> Path:
        return self.summaries_runs_dir / self.run_id

    @property
    def run_config_dir(self) -> Path:
        return self.summaries_run_dir / "config"

    @property
    def run_reports_dir(self) -> Path:
        return self.summaries_run_dir / "reports"

    @property
    def run_plots_dir(self) -> Path:
        return self.summaries_run_dir / "plots"

    @property
    def run_data_dir(self) -> Path:
        return self.summaries_run_dir / "data"

    @property
    def run_logs_dir(self) -> Path:
        return self.summaries_run_dir / "logs"

    @property
    def run_tearsheets_dir(self) -> Path:
        return self.summaries_run_dir / "tearsheets"

    @property
    def summaries_latest_link(self) -> Path:
        return self.summaries_root_dir / "latest"

    def prepare_summaries_run_dir(self) -> Path:
        run_dir = self.summaries_run_dir
        run_dir.mkdir(parents=True, exist_ok=True)

        # Pre-create standard subdirectories
        for d in [
            self.run_config_dir,
            self.run_reports_dir,
            self.run_plots_dir,
            self.run_data_dir,
            self.run_logs_dir,
            self.run_tearsheets_dir,
        ]:
            d.mkdir(parents=True, exist_ok=True)

        return run_dir

    def promote_summaries_latest(self) -> None:
        run_dir = self.prepare_summaries_run_dir()
        self._ensure_latest_symlink(run_dir)

    def _ensure_latest_symlink(self, run_dir: Path) -> None:
        latest = self.summaries_latest_link
        runs_rel_target = Path("runs") / self.run_id

        latest.parent.mkdir(parents=True, exist_ok=True)
        self.summaries_runs_dir.mkdir(parents=True, exist_ok=True)

        legacy_latest = self.summaries_runs_dir / "latest"
        if legacy_latest.exists() and not legacy_latest.is_symlink():
            try:
                backup_name = f"legacy_runs_latest_{datetime.now().strftime('%Y%m%d-%H%M%S')}"
                legacy_latest.rename(self.summaries_runs_dir / backup_name)
            except Exception:
                return

        if latest.exists() and not latest.is_symlink() and latest.is_dir():
            try:
                if any(latest.iterdir()):
                    backup_name = f"legacy_latest_{datetime.now().strftime('%Y%m%d-%H%M%S')}"
                    latest.rename(self.summaries_runs_dir / backup_name)
                else:
                    latest.rmdir()
            except Exception:
                return

        if latest.is_symlink() or latest.exists():
            try:
                latest.unlink()
            except Exception:
                return

        try:
            latest.symlink_to(runs_rel_target, target_is_directory=True)
        except OSError:
            import shutil

            if latest.exists():
                try:
                    if latest.is_file() or latest.is_symlink():
                        latest.unlink()
                    else:
                        shutil.rmtree(latest)
                except Exception:
                    return

            try:
                shutil.copytree(run_dir, latest)
                (latest / "LATEST").write_text(self.run_id + "\n", encoding="utf-8")
            except Exception:
                return


TradingViewScraperSettings.model_rebuild()


class ThreadSafeConfig:
    """
    Singleton manager for thread-safe configuration access.

    Implements the ThreadSafeConfig pattern using ContextVars for task-local isolation
    while maintaining a global singleton fallback for legacy code.
    """

    _instance: ClassVar[TradingViewScraperSettings | None] = None
    _context: ClassVar[ContextVar[TradingViewScraperSettings | None]] = ContextVar("settings_ctx", default=None)
    _lock: ClassVar[Lock] = Lock()

    @classmethod
    def get(cls) -> TradingViewScraperSettings:
        # 1. Check Context (Priority)
        if (ctx := cls._context.get()) is not None:
            return ctx

        # 2. Check Global Singleton (Double-checked locking)
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = TradingViewScraperSettings()
        assert cls._instance is not None
        return cls._instance

    @classmethod
    def set_active(cls, settings: TradingViewScraperSettings) -> Token:
        return cls._context.set(settings)

    @classmethod
    def reset_active(cls, token: Token) -> None:
        cls._context.reset(token)

    @classmethod
    def clear_global_cache(cls) -> None:
        """Forces a reload of the global singleton (useful for tests/legacy scripts)."""
        with cls._lock:
            cls._instance = None
            logger.debug("Global settings cache cleared")


def get_settings() -> TradingViewScraperSettings:
    """
    Thread-safe settings retrieval following context isolation principles.

    Returns:
        TradingViewScraperSettings: The active context settings if set,
                                    falling back to cached global settings.
    """
    return ThreadSafeConfig.get()


def set_active_settings(settings: TradingViewScraperSettings) -> Token:
    """
    Sets the active settings for the current context (thread/task).

    Args:
        settings: The settings instance to activate.
    """
    return ThreadSafeConfig.set_active(settings)


def clear_settings_cache():
    """
    Clears the global settings cache, forcing a reload from environment and manifest.
    Deprecated: Prefer using dependency injection or set_active_settings.
    """
    ThreadSafeConfig.clear_global_cache()


def inspect_active_settings() -> dict[str, Any]:
    """
    Returns the active configuration as a dictionary for discoverability and auditing.

    Returns:
        dict[str, Any]: Flat dictionary of current configuration parameters.
    """
    return get_settings().model_dump()


def debug_settings():
    """Prints the current active settings for debugging purposes."""
    print(json.dumps(inspect_active_settings(), indent=2, default=str))


if __name__ == "__main__":
    # Helper for Makefile/CLI to export variables from the manifest
    settings = get_settings()
    if "--export-env" in sys.argv:
        # Map pydantic field names to institutional ENV names
        mapping = {
            "lookback_days": "LOOKBACK",
            "batch_size": "BATCH",
            "backfill": "BACKFILL",
            "gapfill": "GAPFILL",
            "strict_health": "STRICT_HEALTH",
            "min_days_floor": "PORTFOLIO_MIN_DAYS_FLOOR",
            "top_n": "TOP_N",
            "threshold": "THRESHOLD",
            "min_momentum_score": "MIN_MOMENTUM_SCORE",
            "cluster_cap": "CLUSTER_CAP",
            "train_window": "BACKTEST_TRAIN",
            "test_window": "BACKTEST_TEST",
            "step_size": "BACKTEST_STEP",
            "backtest_simulator": "BACKTEST_SIMULATOR",
            "backtest_simulators": "BACKTEST_SIMULATORS",
            "backtest_slippage": "BACKTEST_SLIPPAGE",
            "backtest_commission": "BACKTEST_COMMISSION",
            "backtest_cash_asset": "BACKTEST_CASH_ASSET",
            "benchmark_symbols": "BENCHMARK_SYMBOLS",
            "report_mode": "REPORT_MODE",
            "dynamic_universe": "DYNAMIC_UNIVERSE",
            "raw_pool_universe": "RAW_POOL_UNIVERSE",
            "engines": "TOURNAMENT_ENGINES",
            "profiles": "TOURNAMENT_PROFILES",
            "gist_id": "GIST_ID",
            "profile": "PROFILE",
            "run_id": "TV_RUN_ID",
            "mandatory_vars": "MANDATORY_VARS",
            "optional_vars": "OPTIONAL_VARS",
            "features.selection_mode": "TV_FEATURES__SELECTION_MODE",
            "features.feat_rebalance_mode": "TV_FEATURES__FEAT_REBALANCE_MODE",
            "features.feat_rebalance_tolerance": "TV_FEATURES__FEAT_REBALANCE_TOLERANCE",
            "features.rebalance_drift_limit": "TV_FEATURES__REBALANCE_DRIFT_LIMIT",
            "features.entropy_max_threshold": "TV_FEATURES__ENTROPY_MAX",
            "features.efficiency_min_threshold": "TV_FEATURES__EFFICIENCY_MIN",
            "features.hurst_random_walk_min": "TV_FEATURES__HURST_RW_MIN",
            "features.hurst_random_walk_max": "TV_FEATURES__HURST_RW_MAX",
            "features.kappa_shrinkage_threshold": "TV_FEATURES__KAPPA_SHRINKAGE_THRESHOLD",
            "features.default_shrinkage_intensity": "TV_FEATURES__DEFAULT_SHRINKAGE_INTENSITY",
            "features.adaptive_fallback_profile": "TV_FEATURES__ADAPTIVE_FALLBACK_PROFILE",
            "portfolio_lookback_days": "PORTFOLIO_LOOKBACK_DAYS",
            "portfolio_batch_size": "PORTFOLIO_BATCH_SIZE",
            "portfolio_backfill": "PORTFOLIO_BACKFILL",
            "portfolio_gapfill": "PORTFOLIO_GAPFILL",
            "portfolio_force_sync": "PORTFOLIO_FORCE_SYNC",
            "portfolio_dedupe_base": "PORTFOLIO_DEDUPE_BASE",
            "data_dir": "TV_DATA_DIR",
            "artifacts_dir": "TV_ARTIFACTS_DIR",
            "export_dir": "TV_EXPORT_DIR",
            "lakehouse_dir": "TV_LAKEHOUSE_DIR",
        }
        for field, env_name in mapping.items():
            if field == "portfolio_lookback_days":
                val = settings.resolve_portfolio_lookback_days()
            elif "." in field:
                parts = field.split(".")
                obj = settings
                for p in parts:
                    obj = getattr(obj, p)
                val = obj
            else:
                val = getattr(settings, field)

            if isinstance(val, bool):
                val = "1" if val else "0"
            elif isinstance(val, list):
                val = ",".join(val)
            print(f"export {env_name}={val}")

        # Export Feature Flags (Only boolean 'feat_' toggles)
        for feat_name, val in settings.features.model_dump().items():
            if feat_name.startswith("feat_") and isinstance(val, bool):
                env_val = "1" if val else "0"
                print(f"export TV_FEATURES__{feat_name.upper()}={env_val}")
