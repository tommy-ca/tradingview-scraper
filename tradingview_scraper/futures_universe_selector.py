"""Futures trend-following universe selector and CLI helper.

This module builds on the existing tradingview-scraper Screener/Overview APIs
to construct a configurable selector for commodity futures. It supports config
loading (JSON/YAML), payload construction, pagination, post-filtering for
liquidity/volatility/trend rules, and optional export of results.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple, Union

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

from tradingview_scraper.symbols.overview import Overview
from tradingview_scraper.symbols.screener import Screener
from tradingview_scraper.symbols.utils import save_csv_file, save_json_file

try:
    import yaml
except ImportError:  # pragma: no cover - optional dependency
    yaml = None

STABLE_BASES = {
    "USDT",
    "USDC",
    "USD",
    "BUSD",
    "FDUSD",
    "TUSD",
    "DAI",
    "PAX",
    "USDP",
    "EUR",
    "GBP",
    "BIDR",
    "TRY",
    "BRL",
    "MXN",
    "ZAR",
    "UST",
    "USTC",
    "CHF",
    "JPY",
    "AEUR",
    "FUSD",
    "FUSDT",
    "USDS",
    "ZUSD",
    "USDM",
}


logger = logging.getLogger(__name__)

DEFAULT_COLUMNS = [
    "name",
    "close",
    "volume",
    "change",
    "Recommend.All",
    "ADX",
    "Volatility.D",
    "Perf.W",
    "Perf.1M",
    "Perf.3M",
    "ATR",
]


DEFAULT_MOMENTUM = {"Perf.1M": 0.0, "Perf.3M": 0.0}

TABLE_DISPLAY_COLUMNS = [
    "symbol",
    "name",
    "close",
    "volume",
    "change",
    "Recommend.All",
    "ADX",
    "Volatility.D",
    "Perf.W",
    "Perf.1M",
    "Perf.3M",
]


class ExportConfig(BaseModel):
    enabled: bool = False
    type: str = "json"

    @field_validator("type")
    @classmethod
    def validate_type(cls, value: str) -> str:
        if value not in {"json", "csv"}:
            raise ValueError("export.type must be 'json' or 'csv'")
        return value


class VolumeConfig(BaseModel):
    min: float = 0.0
    value_traded_min: float = 0.0
    per_exchange: Dict[str, float] = Field(default_factory=dict)


class VolatilityConfig(BaseModel):
    min: Optional[float] = None
    max: Optional[float] = None
    atr_pct_max: Optional[float] = None
    fallback_use_atr_pct: bool = True
    use_value_traded_floor: bool = False

    @model_validator(mode="after")
    def validate_bounds(self) -> "VolatilityConfig":
        if self.min is not None and self.max is not None and self.min > self.max:
            raise ValueError("volatility.min cannot exceed volatility.max")
        return self


class TrendRuleConfig(BaseModel):
    enabled: bool = True
    min: Optional[float] = None
    horizons: Dict[str, float] = Field(default_factory=dict)


class TrendConfig(BaseModel):
    logic: str = "AND"
    timeframe: str = "monthly"
    direction: str = "long"
    recommendation: TrendRuleConfig = Field(default_factory=lambda: TrendRuleConfig(min=0.3))
    adx: TrendRuleConfig = Field(default_factory=lambda: TrendRuleConfig(min=20))
    momentum: TrendRuleConfig = Field(default_factory=lambda: TrendRuleConfig(horizons=DEFAULT_MOMENTUM))
    confirmation_momentum: TrendRuleConfig = Field(default_factory=lambda: TrendRuleConfig(enabled=False, horizons={}))

    @field_validator("logic")
    @classmethod
    def validate_logic(cls, value: str) -> str:
        value_upper = value.upper()
        if value_upper not in {"AND", "OR"}:
            raise ValueError("trend.logic must be AND or OR")
        return value_upper

    @field_validator("timeframe")
    @classmethod
    def validate_timeframe(cls, value: str) -> str:
        value_lower = value.lower()
        if value_lower not in {"daily", "weekly", "monthly"}:
            raise ValueError("trend.timeframe must be daily, weekly, or monthly")
        return value_lower

    @field_validator("direction")
    @classmethod
    def validate_direction(cls, value: str) -> str:
        value_lower = value.lower()
        if value_lower not in {"long", "short"}:
            raise ValueError("trend.direction must be long or short")
        return value_lower


class ScreenConfig(BaseModel):
    timeframe: str
    logic: str = "AND"
    direction: str = "long"
    recommendation: TrendRuleConfig = Field(default_factory=TrendRuleConfig)
    adx: TrendRuleConfig = Field(default_factory=TrendRuleConfig)
    momentum: TrendRuleConfig = Field(default_factory=TrendRuleConfig)
    osc: TrendRuleConfig = Field(default_factory=TrendRuleConfig)
    volatility: TrendRuleConfig = Field(default_factory=TrendRuleConfig)

    @field_validator("logic")
    @classmethod
    def validate_logic(cls, value: str) -> str:
        value_upper = value.upper()
        if value_upper not in {"AND", "OR"}:
            raise ValueError("screen.logic must be AND or OR")
        return value_upper

    @field_validator("timeframe")
    @classmethod
    def validate_timeframe(cls, value: str) -> str:
        value_lower = value.lower()
        if value_lower not in {"daily", "weekly", "monthly"}:
            raise ValueError("screen.timeframe must be daily, weekly, or monthly")
        return value_lower

    @field_validator("direction")
    @classmethod
    def validate_direction(cls, value: str) -> str:
        value_lower = value.lower()
        if value_lower not in {"long", "short"}:
            raise ValueError("screen.direction must be long or short")
        return value_lower


class ExportMetadata(BaseModel):
    symbol: str = "futures_universe"
    data_category: str = "universe_selector"


class SelectorConfig(BaseModel):
    markets: List[str] = Field(default_factory=lambda: ["futures"])
    exchanges: List[str] = Field(default_factory=list)
    filters: List[Dict[str, Any]] = Field(default_factory=list)
    include_symbols: List[str] = Field(default_factory=list)
    exclude_symbols: List[str] = Field(default_factory=list)
    include_perps_only: bool = False
    exclude_perps: bool = False
    exclude_dated_futures: bool = False
    include_dated_futures_only: bool = False
    columns: List[str] = Field(default_factory=lambda: DEFAULT_COLUMNS.copy())
    volume: VolumeConfig = Field(default_factory=VolumeConfig)
    volatility: VolatilityConfig = Field(default_factory=VolatilityConfig)
    trend: TrendConfig = Field(default_factory=TrendConfig)
    trend_screen: Optional[ScreenConfig] = None
    confirm_screen: Optional[ScreenConfig] = None
    execute_screen: Optional[ScreenConfig] = None  # optional; downstream execution can be handled separately
    sort_by: str = "volume"
    sort_order: str = "desc"
    final_sort_by: Optional[str] = None
    final_sort_order: str = "desc"
    momentum_composite_fields: List[str] = Field(default_factory=list)
    momentum_composite_field_name: str = "momentum_zscore"
    prefilter_limit: Optional[int] = None
    limit: int = 100
    pagination_size: int = 50
    retries: int = 2
    timeout: int = 10
    dedupe_by_symbol: bool = False
    attach_perp_counterparts: bool = False
    base_from_spot_only: bool = False
    allowed_spot_quotes: List[str] = Field(default_factory=list)
    base_currencies: List[str] = Field(default_factory=list)  # Filter by base currency
    ensure_symbols: List[str] = Field(default_factory=list)
    exclude_stable_bases: bool = False
    prefer_perps: bool = False
    perp_exchange_priority: List[str] = Field(default_factory=list)
    market_cap_file: Optional[str] = None
    market_cap_limit: Optional[int] = None
    market_cap_rank_limit: Optional[int] = None
    market_cap_floor: Optional[float] = None
    market_cap_require_hit: bool = False
    base_universe_limit: Optional[int] = None
    base_universe_sort_by: str = "Value.Traded"
    export: ExportConfig = Field(default_factory=ExportConfig)
    export_metadata: ExportMetadata = Field(default_factory=ExportMetadata)

    @field_validator("sort_order", "final_sort_order")
    @classmethod
    def validate_sort_order(cls, value: str) -> str:
        value_lower = value.lower()
        if value_lower not in {"asc", "desc"}:
            raise ValueError("sort_order must be 'asc' or 'desc'")
        return value_lower

    @field_validator("limit", "pagination_size", "retries", "timeout", "prefilter_limit")
    @classmethod
    def validate_positive(cls, value: Optional[int], info: Any) -> Optional[int]:
        if value is None:
            return value
        if value <= 0:
            raise ValueError(f"{info.field_name} must be positive")
        return value

    @model_validator(mode="after")
    def validate_markets(self) -> "SelectorConfig":
        if not self.markets:
            raise ValueError("At least one market must be provided")
        return self


def _merge(base: Dict[str, Any], override: Mapping[str, Any]) -> Dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, Mapping) and isinstance(result.get(key), Mapping):
            result[key] = _merge(result[key], value)
        else:
            result[key] = value
    return result


def _load_config_file(path: str) -> Dict[str, Any]:
    path_obj = Path(path)
    if not path_obj.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    ext = path_obj.suffix.lower()
    with path_obj.open("r", encoding="utf-8") as handle:
        if ext in {".yaml", ".yml"}:
            if yaml is None:
                raise ImportError("PyYAML is required to load YAML configs")
            raw = yaml.safe_load(handle) or {}
        else:
            raw = json.load(handle)

    # Handle base_preset inheritance
    if "base_preset" in raw:
        preset_path = raw.pop("base_preset")
        if not Path(preset_path).is_absolute():
            preset_path = path_obj.parent / preset_path
        base = _load_config_file(str(preset_path))
        raw = _merge(base, raw)

    return raw


def load_config(
    source: Optional[Union[str, Mapping[str, Any]]] = None,
    overrides: Optional[Mapping[str, Any]] = None,
) -> SelectorConfig:
    """Load selector config from a file or mapping."""
    raw: Dict[str, Any] = {}
    if isinstance(source, Mapping):
        raw = dict(source)
    elif isinstance(source, str):
        raw = _load_config_file(source)
    elif source is not None:
        raise TypeError("source must be a mapping, path string, or None")

    if overrides:
        raw = _merge(raw, overrides)

    return SelectorConfig.model_validate(raw)


class FuturesUniverseSelector:
    """Selector orchestrating Screener + post-filters for futures."""

    REQUIRED_COLUMNS = ["name", "close", "volume", "change", "Recommend.All"]

    def __init__(
        self,
        config: Optional[Union[str, Mapping[str, Any], SelectorConfig]] = None,
        screener: Optional[Screener] = None,
        overview: Optional[Overview] = None,
    ) -> None:
        self.config = config if isinstance(config, SelectorConfig) else load_config(config)

        # Auto-fix export symbol if default and market is different
        if self.config.export_metadata.symbol == "futures_universe" and self.config.markets:
            market_name = self.config.markets[0]
            if market_name != "futures":
                self.config.export_metadata.symbol = f"{market_name}_universe"

        self.screener = screener or Screener(export_result=False)
        self.overview = overview or Overview(export_result=False)
        self._market_cap_map: Optional[Dict[str, float]] = None

    def _build_columns(self) -> List[str]:
        columns: List[str] = []
        for col in self.REQUIRED_COLUMNS + self.config.columns:
            if col not in columns:
                columns.append(col)

        if self.config.volume.value_traded_min > 0 and "Value.Traded" not in columns:
            columns.append("Value.Traded")

        if self.config.market_cap_floor is not None and "market_cap_calc" not in columns:
            columns.append("market_cap_calc")

        if self.config.trend.timeframe in {"daily", "weekly"} and "Perf.W" not in columns:
            columns.append("Perf.W")
        return columns

    def _build_filters(self, market: str) -> List[Dict[str, Any]]:
        filters: List[Dict[str, Any]] = []
        type_value = None
        if market == "futures":
            type_value = "futures"
        elif market == "forex":
            type_value = "forex"

        if type_value:
            filters.append({"left": "type", "operation": "equal", "right": type_value})

        if self.config.volume.min:
            filters.append(
                {
                    "left": "volume",
                    "operation": "greater",
                    "right": self.config.volume.min,
                }
            )

        if self.config.volume.value_traded_min > 0:
            filters.append(
                {
                    "left": "Value.Traded",
                    "operation": "greater",
                    "right": self.config.volume.value_traded_min,
                }
            )

        if self.config.filters:
            filters.extend(self.config.filters)

        return filters

    def _screen_market(
        self,
        market: str,
        filters: List[Dict[str, Any]],
        columns: List[str],
        exchange: Optional[str] = None,
        max_rows: Optional[int] = None,
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        collected: List[Dict[str, Any]] = []
        errors: List[str] = []
        offset = 0
        page_size = self.config.pagination_size
        target = max_rows or self.config.limit

        while len(collected) < target:
            remaining = target - len(collected)
            batch_size = min(page_size, remaining)
            filters_with_exchange = list(filters)
            if exchange:
                filters_with_exchange = filters_with_exchange + [{"left": "exchange", "operation": "equal", "right": exchange}]
            response = self.screener.screen(
                market=market,
                filters=filters_with_exchange,
                columns=columns,
                sort_by=self.config.sort_by,
                sort_order=self.config.sort_order,
                limit=batch_size,
                range_start=offset,
            )

            if not response or response.get("status") != "success":
                errors.append(response.get("error", f"Failed to screen market {market}"))
                break

            data = response.get("data", [])
            if not data:
                break

            collected.extend(data)
            if len(data) < batch_size:
                break
            offset += batch_size

        return collected, errors

    @staticmethod
    def _extract_exchange(symbol: str) -> Optional[str]:
        if not symbol or ":" not in symbol:
            return None
        return symbol.split(":", 1)[0]

    @staticmethod
    def _extract_base_quote(symbol: str) -> Tuple[str, str]:
        if not symbol:
            return "", ""
        core = symbol.split(":", 1)[-1].upper().replace(".P", "")
        for stable in sorted(STABLE_BASES, key=len, reverse=True):
            if core.endswith(stable) and len(core) > len(stable):
                return core[: -len(stable)], stable
        return core, ""

    @staticmethod
    def _base_symbol(symbol: str) -> str:
        base, _ = FuturesUniverseSelector._extract_base_quote(symbol)
        return base

    @staticmethod
    def _is_perp(symbol: str) -> bool:
        return bool(symbol) and symbol.upper().endswith(".P")

    @staticmethod
    def _is_spot_symbol(symbol: str) -> bool:
        base, quote = FuturesUniverseSelector._extract_base_quote(symbol)
        return bool(base) and bool(quote)

    @staticmethod
    def _is_dated_symbol(symbol: str) -> bool:
        if not symbol:
            return False
        core = symbol.split(":", 1)[-1].upper().replace(".P", "")
        patterns = [r"[0-9]{1,2}[A-Z][0-9]{2,4}$", r"[A-Z]{1,3}[0-9]{2,4}$"]
        return any(re.search(pat, core) for pat in patterns)

    def _evaluate_liquidity(self, row: Dict[str, Any]) -> bool:
        volume_value = row.get("volume")
        value_traded = row.get("Value.Traded")
        vt_floor = self.config.volume.value_traded_min or 0
        vol_floor = self.config.volume.min or 0

        # If Value.Traded is present, enforce that floor first
        if value_traded is not None and value_traded < vt_floor:
            return False

        if volume_value is None:
            return vol_floor <= 0
        symbol = row.get("symbol", "")
        exchange = self._extract_exchange(symbol)
        if exchange and exchange in self.config.volume.per_exchange:
            threshold = self.config.volume.per_exchange[exchange]
        else:
            threshold = self.config.volume.min
        return volume_value >= threshold

    def _evaluate_volatility(self, row: Dict[str, Any]) -> Tuple[bool, Optional[float]]:
        vol_cfg = self.config.volatility
        volatility_value = row.get("Volatility.D")
        atr_pct: Optional[float] = None

        if vol_cfg.fallback_use_atr_pct:
            atr = row.get("ATR")
            close = row.get("close")
            if atr is not None and close not in (None, 0):
                atr_pct = atr / close
                row["atr_pct"] = atr_pct

        checks_present = any(value is not None for value in (vol_cfg.min, vol_cfg.max, vol_cfg.atr_pct_max))
        if not checks_present:
            return True, atr_pct

        if volatility_value is not None:
            above_min = vol_cfg.min is None or volatility_value >= vol_cfg.min
            below_max = vol_cfg.max is None or volatility_value <= vol_cfg.max
            if above_min and below_max:
                return True, atr_pct

        if atr_pct is not None and vol_cfg.atr_pct_max is not None:
            if atr_pct <= vol_cfg.atr_pct_max:
                return True, atr_pct

        return False, atr_pct

    def _evaluate_trend(self, row: Dict[str, Any]) -> Dict[str, bool]:
        trend_cfg = self.config.trend
        checks: Dict[str, bool] = {}
        is_long = trend_cfg.direction == "long"

        if trend_cfg.recommendation.enabled:
            rec_min = trend_cfg.recommendation.min
            rec_value = row.get("Recommend.All")
            rec_pass = False
            if rec_min is not None and rec_value is not None:
                rec_pass = rec_value >= rec_min if is_long else rec_value <= rec_min
            checks["recommendation"] = rec_pass

        if trend_cfg.adx.enabled:
            adx_min = trend_cfg.adx.min
            adx_value = row.get("ADX")
            checks["adx"] = adx_min is not None and adx_value is not None and adx_value >= adx_min

        if trend_cfg.momentum.enabled:
            horizons = trend_cfg.momentum.horizons or {}
            if horizons == DEFAULT_MOMENTUM:
                if trend_cfg.timeframe == "daily":
                    horizons = {"change": 0.0, "Perf.W": 0.0}
                elif trend_cfg.timeframe == "weekly":
                    horizons = {"Perf.W": 0.0}
            if not horizons:
                if trend_cfg.timeframe == "daily":
                    horizons = {"change": 0.0, "Perf.W": 0.0}
                elif trend_cfg.timeframe == "weekly":
                    horizons = {"Perf.W": 0.0}
                else:
                    horizons = DEFAULT_MOMENTUM

            momentum_pass = True
            for field, threshold in horizons.items():
                value = row.get(field)
                if value is None:
                    momentum_pass = False
                    break
                if is_long:
                    if value <= threshold:
                        momentum_pass = False
                        break
                else:
                    if value >= threshold:
                        momentum_pass = False
                        break
            checks["momentum"] = momentum_pass

        if trend_cfg.confirmation_momentum.enabled:
            conf_pass = True
            for field, threshold in (trend_cfg.confirmation_momentum.horizons or {}).items():
                value = row.get(field)
                if value is None:
                    conf_pass = False
                    break
                if is_long:
                    if value <= threshold:
                        conf_pass = False
                        break
                else:
                    if value >= threshold:
                        conf_pass = False
                        break
            checks["confirmation_momentum"] = conf_pass

        enabled_checks = {k: v for k, v in checks.items() if v is not None}
        if not enabled_checks:
            combined = True
        elif trend_cfg.logic == "AND":
            combined = all(enabled_checks.values())
        else:
            combined = any(enabled_checks.values())

        checks["combined"] = combined
        return checks

    def _evaluate_screen(self, row: Dict[str, Any], screen: ScreenConfig) -> Dict[str, bool]:
        checks: Dict[str, bool] = {}
        is_long = screen.direction == "long"

        if screen.recommendation.enabled:
            rec_min = screen.recommendation.min
            rec_value = row.get("Recommend.All")
            if rec_min is None:
                rec_pass = True
            else:
                rec_pass = False
                if rec_value is not None:
                    rec_pass = rec_value >= rec_min if is_long else rec_value <= rec_min
            checks["recommendation"] = rec_pass

        if screen.adx.enabled:
            adx_min = screen.adx.min
            adx_value = row.get("ADX")
            if adx_min is None:
                checks["adx"] = True
            else:
                checks["adx"] = adx_value is not None and adx_value >= adx_min

        if screen.momentum.enabled:
            horizons = screen.momentum.horizons or {}
            if not horizons:
                checks["momentum"] = True
            else:
                momentum_pass = True
                for field, threshold in horizons.items():
                    value = row.get(field)
                    if value is None:
                        momentum_pass = False
                        break
                    if is_long:
                        if value <= threshold:
                            momentum_pass = False
                            break
                    else:
                        if value >= threshold:
                            momentum_pass = False
                            break
                checks["momentum"] = momentum_pass

        if screen.osc.enabled:
            horizons = screen.osc.horizons or {}
            if not horizons:
                checks["osc"] = True
            else:
                osc_pass = True
                for field, threshold in horizons.items():
                    value = row.get(field)
                    if value is None:
                        osc_pass = False
                        break
                    if is_long:
                        if value >= threshold:
                            osc_pass = False
                            break
                    else:
                        if value <= threshold:
                            osc_pass = False
                            break
                checks["osc"] = osc_pass

        if screen.volatility.enabled:
            horizons = screen.volatility.horizons or {}
            if not horizons:
                checks["volatility"] = True
            else:
                vol_pass = True
                for field, threshold in horizons.items():
                    value = row.get(field)
                    if value is None:
                        vol_pass = False
                        break
                    if is_long:
                        if value >= threshold:
                            vol_pass = False
                            break
                    else:
                        if value <= threshold:
                            vol_pass = False
                            break
                checks["volatility"] = vol_pass

        enabled_checks = {k: v for k, v in checks.items() if v is not None}
        if not enabled_checks:
            combined = True
        elif screen.logic == "AND":
            combined = all(enabled_checks.values())
        else:
            combined = any(enabled_checks.values())

        checks["combined"] = combined
        return checks

    def _apply_basic_filters(self, rows: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        include_set = set(s.upper() for s in self.config.include_symbols)
        exclude_set = set(s.upper() for s in self.config.exclude_symbols)
        exchange_set = set(self.config.exchanges)

        filtered: List[Dict[str, Any]] = []
        for row in rows:
            symbol = row.get("symbol", "").upper()
            exchange = self._extract_exchange(symbol)
            base_symbol = self._base_symbol(symbol)

            if self.config.exclude_stable_bases and base_symbol in STABLE_BASES:
                continue

            is_perp = symbol.endswith(".P")
            is_dated = self._is_dated_symbol(symbol)

            if self.config.include_dated_futures_only and not is_dated:
                continue
            if self.config.exclude_dated_futures and is_dated:
                continue

            if self.config.allowed_spot_quotes and not is_perp:
                _, quote = self._extract_base_quote(symbol)
                if not quote or quote not in self.config.allowed_spot_quotes:
                    continue

            if self.config.base_currencies and not is_perp:
                base, _ = self._extract_base_quote(symbol)
                if not base or base not in self.config.base_currencies:
                    continue

            if self.config.include_perps_only and not is_perp:
                continue
            if self.config.exclude_perps and is_perp:
                continue

            if include_set and symbol not in include_set:
                continue
            if symbol in exclude_set:
                continue
            if exchange_set and exchange not in exchange_set:
                continue

            filtered.append(row)
        return filtered

    def _apply_strategy_filters(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        filtered: List[Dict[str, Any]] = []
        for row in rows:
            passes = row.get("passes", {}) if "passes" in row else {}
            trend_checks = self._evaluate_trend(row)
            passes.update({f"trend_{k}": v for k, v in trend_checks.items()})

            screens_combined = True
            if trend_checks.get("combined", True):
                if self.config.trend_screen:
                    screen_checks = self._evaluate_screen(row, self.config.trend_screen)
                    passes.update({f"trend_screen_{k}": v for k, v in screen_checks.items()})
                    screens_combined = screens_combined and screen_checks.get("combined", True)
                if screens_combined and self.config.confirm_screen:
                    confirm_checks = self._evaluate_screen(row, self.config.confirm_screen)
                    passes.update({f"confirm_screen_{k}": v for k, v in confirm_checks.items()})
                    screens_combined = screens_combined and confirm_checks.get("combined", True)
                if screens_combined and self.config.execute_screen:
                    execute_checks = self._evaluate_screen(row, self.config.execute_screen)
                    passes.update({f"execute_screen_{k}": v for k, v in execute_checks.items()})
                    screens_combined = screens_combined and execute_checks.get("combined", True)

            passes["all"] = trend_checks.get("combined", True) and screens_combined
            row["passes"] = passes
            if passes["all"]:
                filtered.append(row)
        return filtered

    def _apply_momentum_composite(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        fields = [f for f in self.config.momentum_composite_fields if f]
        if not fields:
            return rows

        stats = {}
        for field in fields:
            values = [float(r[field]) for r in rows if isinstance(r.get(field), (int, float))]
            if not values:
                continue
            mean_val = sum(values) / len(values)
            variance = sum((v - mean_val) ** 2 for v in values) / len(values)
            std_val = variance**0.5
            if std_val > 0:
                stats[field] = (mean_val, std_val)

        composite_field = self.config.momentum_composite_field_name or "momentum_zscore"
        if not stats:
            for row in rows:
                row[composite_field] = None
            return rows

        for row in rows:
            scores = []
            for field, (mean_val, std_val) in stats.items():
                val = row.get(field)
                if isinstance(val, (int, float)):
                    scores.append((val - mean_val) / std_val)
            row[composite_field] = sum(scores) / len(scores) if scores else None

        return rows

    def _load_market_cap_map(self) -> Dict[str, float]:
        if self._market_cap_map is not None:
            return self._market_cap_map
        path = self.config.market_cap_file
        if not path:
            self._market_cap_map = {}
            return self._market_cap_map
        path_obj = Path(path)
        if not path_obj.exists():
            logging.warning("Market cap file not found: %s", path)
            self._market_cap_map = {}
            return self._market_cap_map
        caps: Dict[str, float] = {}
        try:
            if path_obj.suffix.lower() == ".json":
                with path_obj.open("r", encoding="utf-8") as handle:
                    payload = json.load(handle)
                if isinstance(payload, dict):
                    for key, val in payload.items():
                        try:
                            caps[str(key).upper()] = float(val)
                        except (TypeError, ValueError):
                            continue
                elif isinstance(payload, list):
                    for item in payload:
                        if not isinstance(item, Mapping):
                            continue
                        sym = item.get("symbol") or item.get("base")
                        cap_val = item.get("market_cap") or item.get("cap")
                        if sym and isinstance(cap_val, (int, float)):
                            core = str(sym).upper().replace(".P", "")
                            if ":" in core:
                                core = core.split(":", 1)[-1]
                            # strip any stable quote suffix from the market cap key
                            for stable in sorted(STABLE_BASES, key=len, reverse=True):
                                if core.endswith(stable) and len(core) > len(stable):
                                    core = core[: -len(stable)]
                                    break
                            caps[core] = float(cap_val)
            elif path_obj.suffix.lower() in {".csv", ".tsv"}:
                with path_obj.open("r", encoding="utf-8") as handle:
                    reader = csv.DictReader(handle)
                    for row in reader:
                        sym = row.get("symbol") or row.get("base")
                        cap_val = row.get("market_cap") or row.get("cap")
                        if sym and cap_val is not None:
                            try:
                                core = str(sym).upper().replace(".P", "")
                                if ":" in core:
                                    core = core.split(":", 1)[-1]
                                for stable in sorted(STABLE_BASES, key=len, reverse=True):
                                    if core.endswith(stable) and len(core) > len(stable):
                                        core = core[: -len(stable)]
                                        break
                                caps[core] = float(cap_val)
                            except (TypeError, ValueError):
                                continue
        except Exception as exc:  # pragma: no cover - defensive
            logging.warning("Failed to load market cap file %s: %s", path, exc)
            caps = {}
        self._market_cap_map = caps
        return self._market_cap_map

    def _apply_market_cap_filter(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        initial_count = len(rows)
        cap_map = self._load_market_cap_map()

        # Annotate with external market cap for visibility/debugging and for floor guard
        for row in rows:
            base = self._base_symbol(row.get("symbol", ""))
            cap_val = cap_map.get(base)
            if cap_val is not None:
                row["market_cap_external"] = cap_val

        # Guard B: Floor-based (Screener OR External)
        if self.config.market_cap_floor is not None:
            rows = [r for r in rows if max(r.get("market_cap_calc") or 0, r.get("market_cap_external") or 0) >= self.config.market_cap_floor]
            logger.info("Floor guard (%s) reduced rows from %d to %d", self.config.market_cap_floor, initial_count, len(rows))

        # Guard A: Rank-based (from external file)
        if cap_map and self.config.market_cap_rank_limit:
            # select top bases by cap to establish the "Allowed Rank" set
            tops = sorted(((b, v) for b, v in cap_map.items()), key=lambda x: x[1], reverse=True)[: self.config.market_cap_rank_limit]
            allowed_bases = {b for b, _ in tops}
            before_rank = len(rows)
            rows = [r for r in rows if self._base_symbol(r.get("symbol", "")) in allowed_bases]
            logger.info("Rank guard (%d) reduced rows from %d to %d", self.config.market_cap_rank_limit, before_rank, len(rows))

        # market_cap_limit is the old field, keep it for backward compatibility
        if cap_map and self.config.market_cap_limit and not self.config.market_cap_rank_limit:
            tops = sorted(((b, v) for b, v in cap_map.items()), key=lambda x: x[1], reverse=True)[: self.config.market_cap_limit]
            allowed_bases = {b for b, _ in tops}
            rows = [r for r in rows if self._base_symbol(r.get("symbol", "")) in allowed_bases]

        return rows

    def _aggregate_by_base(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        sort_field = self.config.final_sort_by or self.config.sort_by or "Value.Traded"
        descending = (self.config.final_sort_order or "desc").lower() == "desc"
        best_by_base: Dict[str, Dict[str, Any]] = {}
        priority = [p.upper() for p in self.config.perp_exchange_priority]
        quote_priority = {q.upper(): idx for idx, q in enumerate(self.config.allowed_spot_quotes)} if self.config.allowed_spot_quotes else None

        def exchange_rank(symbol: str) -> int:
            exchange = self._extract_exchange(symbol) or ""
            if exchange.upper() in priority:
                return priority.index(exchange.upper())
            return len(priority)

        for row in rows:
            symbol = row.get("symbol", "")
            base = self._base_symbol(symbol)
            current = best_by_base.get(base)
            if current is None:
                best_by_base[base] = row
                continue

            candidate_value = row.get(sort_field)
            best_value = current.get(sort_field)

            if self.config.base_from_spot_only and quote_priority is not None:
                _, cand_quote = self._extract_base_quote(symbol)
                _, best_quote = self._extract_base_quote(current.get("symbol", ""))
                cand_rank = quote_priority.get(cand_quote or "", len(quote_priority))
                best_rank = quote_priority.get(best_quote or "", len(quote_priority))
                if cand_rank < best_rank:
                    best_by_base[base] = row
                    continue
                if best_rank < cand_rank:
                    continue

            if self.config.prefer_perps:
                cand_perp = self._is_perp(symbol)
                best_perp = self._is_perp(current.get("symbol", ""))
                if cand_perp and not best_perp:
                    best_by_base[base] = row
                    continue
                if best_perp and not cand_perp:
                    continue
                if cand_perp and best_perp and priority:
                    if exchange_rank(symbol) < exchange_rank(current.get("symbol", "")):
                        best_by_base[base] = row
                        continue

            try:
                if candidate_value is None:
                    continue
                if best_value is None:
                    best_by_base[base] = row
                    continue
                if descending:
                    if candidate_value > best_value:
                        best_by_base[base] = row
                else:
                    if candidate_value < best_value:
                        best_by_base[base] = row
            except TypeError:
                continue

        return list(best_by_base.values())

    def _sort_rows(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        final_sorted = rows
        if self.config.final_sort_by:
            reverse = self.config.final_sort_order == "desc"
            field = self.config.final_sort_by

            def sort_key(row: Dict[str, Any]):
                val = row.get(field)
                if isinstance(val, (int, float)):
                    return val
                return float("-inf") if reverse else float("inf")

            final_sorted = sorted(rows, key=sort_key, reverse=reverse)
        return final_sorted

    def _select_perp_candidate(self, base: str, perps: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        candidates = [p for p in perps if self._base_symbol(p.get("symbol", "")) == base]
        if not candidates:
            return None

        priority = [p.upper() for p in self.config.perp_exchange_priority]
        field = self.config.final_sort_by or self.config.sort_by or "volume"
        reverse = (self.config.final_sort_order or "desc") == "desc"

        def exchange_rank(symbol: str) -> int:
            exchange = self._extract_exchange(symbol) or ""
            if exchange.upper() in priority:
                return priority.index(exchange.upper())
            return len(priority)

        def candidate_key(row: Dict[str, Any]):
            exchange_score = exchange_rank(row.get("symbol", ""))
            val = row.get(field)
            if isinstance(val, (int, float)):
                metric = -val if reverse else val
            else:
                metric = float("inf")
            return (exchange_score, metric)

        return sorted(candidates, key=candidate_key)[0]

    def _attach_perp_counterparts(self, rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        spot_rows: List[Dict[str, Any]] = []
        for r in rows:
            symbol = r.get("symbol", "")
            if self.config.base_from_spot_only:
                if self._is_perp(symbol):
                    continue
                base, quote = self._extract_base_quote(symbol)
                if not (base and quote):
                    continue
                if self.config.allowed_spot_quotes and quote not in self.config.allowed_spot_quotes:
                    continue
                spot_rows.append(r)
            else:
                if not self._is_perp(symbol):
                    spot_rows.append(r)

        perp_rows = [r for r in rows if self._is_perp(r.get("symbol", ""))]

        spot_unique = self._dedupe_by_base(spot_rows)
        spot_sorted = self._sort_rows(spot_unique)
        base_trimmed = spot_sorted[: self.config.limit]

        ensure_set = {s.upper() for s in self.config.ensure_symbols}
        if ensure_set:
            spot_lookup = {(r.get("symbol", "") or "").upper(): r for r in spot_sorted}
            existing = {row.get("symbol") for row in base_trimmed}
            for symbol in ensure_set:
                row = spot_lookup.get(symbol)
                if row and row.get("symbol") not in existing:
                    base_trimmed.append(row)
                    existing.add(row.get("symbol"))

        seen_symbols = {row.get("symbol") for row in base_trimmed}
        extras: List[Dict[str, Any]] = []
        for row in base_trimmed:
            base = self._base_symbol(row.get("symbol", ""))
            perp_candidate = self._select_perp_candidate(base, perp_rows)
            if perp_candidate and perp_candidate.get("symbol") not in seen_symbols:
                extras.append(perp_candidate)
                seen_symbols.add(perp_candidate.get("symbol"))

        return base_trimmed + extras

    def _export_results(self, data: List[Dict[str, Any]]) -> None:
        if not self.config.export.enabled:
            return

        if self.config.export.type == "json":
            save_json_file(
                data=data,
                symbol=self.config.export_metadata.symbol,
                data_category=self.config.export_metadata.data_category,
            )
        else:
            save_csv_file(
                data=data,
                symbol=self.config.export_metadata.symbol,
                data_category=self.config.export_metadata.data_category,
            )

    def run(self, dry_run: bool = False) -> Dict[str, Any]:
        """Execute the selector pipeline."""
        columns = self._build_columns()

        if dry_run:
            return {
                "status": "dry_run",
                "payloads": [
                    {
                        "market": market,
                        "filters": self._build_filters(market),
                        "columns": columns,
                        "sort_by": self.config.sort_by,
                        "sort_order": self.config.sort_order,
                        "limit": self.config.limit,
                        "pagination_size": self.config.pagination_size,
                    }
                    for market in self.config.markets
                ],
                "config": self.config.model_dump(),
            }

        aggregated: List[Dict[str, Any]] = []
        errors: List[str] = []

        filters: List[Dict[str, Any]] = []
        for market in self.config.markets:
            filters = self._build_filters(market)
            prefilter_limit = self.config.prefilter_limit or self.config.limit
            if self.config.exchanges:
                for exchange in self.config.exchanges:
                    market_rows, market_errors = self._screen_market(
                        market,
                        filters,
                        columns,
                        exchange=exchange,
                        max_rows=prefilter_limit,
                    )
                    aggregated.extend(market_rows)
                    errors.extend(market_errors)
            else:
                market_rows, market_errors = self._screen_market(market, filters, columns, max_rows=prefilter_limit)
                aggregated.extend(market_rows)
                errors.extend(market_errors)

        # 1. Basic Filters (Symbol, type, stable exclusion)
        rows = self._apply_basic_filters(aggregated)

        # 2. Market Cap Guard (Rank and Floor)
        rows = self._apply_market_cap_filter(rows)

        # 3. Volatility Filter
        rows = [r for r in rows if self._evaluate_volatility(r)[0]]

        # 4. Liquidity Filter (Floor)
        rows = [r for r in rows if self._evaluate_liquidity(r)]

        # 5. Aggregation (Deduplicate by base currency)
        if self.config.dedupe_by_symbol:
            rows = self._aggregate_by_base(rows)

        # 6. Sorting & Limiting (Base Universe)
        base_sort_field = self.config.base_universe_sort_by or "Value.Traded"
        rows.sort(key=lambda x: x.get(base_sort_field) or 0, reverse=True)

        if self.config.base_universe_limit:
            rows = rows[: self.config.base_universe_limit]

        # 7. Strategy Filters (Trend, Screens)
        # Note: If no trend rules are enabled, this just returns the same rows with 'all: true'
        filtered = self._apply_strategy_filters(rows)

        if self.config.momentum_composite_fields:
            filtered = self._apply_momentum_composite(filtered)

        if self.config.attach_perp_counterparts:
            # Note: attach_perp_counterparts has its own internal dedupe and sort logic
            # which we might want to refactor later to use the common methods.
            trimmed = self._attach_perp_counterparts(filtered)
        else:
            final_sorted = self._sort_rows(filtered)
            trimmed = final_sorted[: self.config.limit]

        if self.config.export.enabled:
            self._export_results(trimmed)

        status = "success" if not errors else "partial_success"
        return {
            "status": status,
            "data": trimmed,
            "filters_applied": {
                "filters": filters,
                "columns": columns,
                "trend_logic": self.config.trend.logic,
            },
            "errors": errors,
            "total_candidates": len(aggregated),
            "total_selected": len(trimmed),
        }


def _format_markdown_table(rows: List[Mapping[str, Any]], columns: Optional[List[str]] = None) -> str:
    if not rows:
        return "No data"

    configured_cols = columns or []
    ordered_cols: List[str] = []
    seen = set()

    for col in ["symbol"] + [c for c in configured_cols if c != "symbol"]:
        if col in seen:
            continue
        if any(col in row for row in rows):
            ordered_cols.append(col)
            seen.add(col)

    if not ordered_cols:
        for key in rows[0].keys():
            if key not in seen:
                ordered_cols.append(key)
                seen.add(key)

    header = "| " + " | ".join(ordered_cols) + " |"
    separator = "| " + " | ".join("---" for _ in ordered_cols) + " |"
    data_lines: List[str] = []

    for row in rows:
        cells = []
        for col in ordered_cols:
            value = row.get(col, "")
            if isinstance(value, float):
                cell = f"{value:.6g}"
            elif isinstance(value, bool):
                cell = "true" if value else "false"
            elif value is None:
                cell = ""
            else:
                cell = str(value)
            cells.append(cell)
        data_lines.append("| " + " | ".join(cells) + " |")

    return "\n".join([header, separator, *data_lines])


def load_config_from_env(env_var: str = "FUTURES_SELECTOR_CONFIG") -> SelectorConfig:
    """Load config from a JSON string stored in an environment variable."""
    payload = os.environ.get(env_var)
    if not payload:
        raise ValueError(f"Environment variable {env_var} is not set")
    return load_config(json.loads(payload))


def _parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Futures trend-following universe selector")
    parser.add_argument("--config", help="Path to YAML/JSON config file")
    parser.add_argument("--limit", type=int, help="Override max results")
    parser.add_argument("--export", choices=["json", "csv"], help="Enable export and set type")
    parser.add_argument(
        "--export-enabled",
        action="store_true",
        help="Enable export of filtered results",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Return payloads without hitting TradingView",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable info-level logging")
    parser.add_argument(
        "--print-format",
        choices=["json", "table"],
        default="json",
        help="Format stdout as pretty JSON or markdown table",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = _parse_args(argv)
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING)

    overrides: Dict[str, Any] = {}
    if args.limit is not None:
        overrides["limit"] = args.limit
    if args.export is not None:
        overrides["export"] = {"enabled": True, "type": args.export}
    elif args.export_enabled:
        overrides["export"] = {"enabled": True}

    try:
        cfg = load_config(args.config, overrides=overrides)
    except (
        FileNotFoundError,
        ValidationError,
        ImportError,
        json.JSONDecodeError,
    ) as exc:  # pragma: no cover - CLI path
        logger.error("Failed to load config: %s", exc)
        return 1

    selector = FuturesUniverseSelector(cfg)
    result = selector.run(dry_run=args.dry_run)

    if args.print_format == "table" and result.get("status") != "dry_run":
        columns = result.get("filters_applied", {}).get("columns")
        table = _format_markdown_table(result.get("data") or [], columns)
        summary = [
            f"status: {result.get('status')}",
            f"total_candidates: {result.get('total_candidates')}",
            f"total_selected: {result.get('total_selected')}",
        ]
        if result.get("errors"):
            summary.append(f"errors: {result.get('errors')}")
        sys.stdout.write("\n".join(summary + [table]))
    else:
        sys.stdout.write(json.dumps(result, indent=2, sort_keys=True, default=str))

    sys.stdout.write("\n")
    return 0 if result.get("status") in {"success", "dry_run"} else 1


__all__ = [
    "FuturesUniverseSelector",
    "load_config",
    "load_config_from_env",
    "SelectorConfig",
    "main",
]


if __name__ == "__main__":  # pragma: no cover - CLI entry
    sys.exit(main())
