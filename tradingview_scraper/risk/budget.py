from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime, time, timezone
from decimal import ROUND_CEILING, Decimal
from pathlib import Path
from typing import Any, Literal, Optional

logger = logging.getLogger("risk.budget")


ReasonCode = Literal[
    "OK",
    "MISSING_STOP",
    "INVALID_E_REF",
    "INVALID_PRICES",
    "DAILY_ENTRIES_EXCEEDED",
    "DAILY_SLICES_EXCEEDED",
    "CAMPAIGN_SLICES_EXCEEDED",
    "ENTRY_TOO_LARGE_FOR_DAILY_CAP",
    "STATE_UNTRUSTED",
]


@dataclass(frozen=True)
class RiskBudgetPolicy:
    total_slices_per_campaign: int = 10
    slice_pct: float = 0.005
    max_entries_per_day: int = 2
    max_slices_per_day: int = 2
    max_slices_per_entry: int = 2
    risk_reset_tz: str = "UTC"
    risk_reset_time: str = "00:00"
    policy_version: str = "daily_slices_v1"


@dataclass(frozen=True)
class EntryIntent:
    """Deterministic input for a single entry decision."""

    account_id: str
    symbol: str
    side: Literal["BUY", "SELL"]
    quantity: float
    expected_entry_price: float
    stop_loss_price: Optional[float]
    intent_id: Optional[str] = None
    ts_utc: Optional[datetime] = None

    def idempotency_key(self) -> str:
        if self.intent_id and str(self.intent_id).strip():
            return str(self.intent_id)

        payload = {
            "account_id": self.account_id,
            "symbol": self.symbol,
            "side": self.side,
            "quantity": float(self.quantity),
            "expected_entry_price": float(self.expected_entry_price),
            "stop_loss_price": float(self.stop_loss_price) if self.stop_loss_price is not None else None,
        }
        raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class EntryDecision:
    allow: bool
    reason_code: ReasonCode
    entry_risk_pct: float
    required_slices: int
    day_key: str
    e_ref: float
    campaign_slices_remaining: int
    entries_today: int
    slices_used_today: int


@dataclass
class RiskBudgetState:
    campaign_slices_remaining: int
    day_key: Optional[str] = None
    e_ref: Optional[float] = None
    entries_today: int = 0
    slices_used_today: int = 0
    # Used for idempotent replay / retries within the campaign scope.
    spent_keys: set[str] = None  # type: ignore[assignment]
    prior_decisions: dict[str, dict[str, Any]] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.spent_keys is None:
            self.spent_keys = set()
        if self.prior_decisions is None:
            self.prior_decisions = {}


def _parse_reset_time(reset_time: str) -> time:
    parts = str(reset_time).split(":")
    if len(parts) != 2:
        raise ValueError(f"Invalid risk_reset_time: {reset_time}")
    hh, mm = int(parts[0]), int(parts[1])
    return time(hour=hh, minute=mm)


def compute_day_key(ts_utc: datetime, tz_name: str, reset_time: str) -> str:
    """Returns the logical risk day key for a timestamp."""
    from zoneinfo import ZoneInfo

    if ts_utc.tzinfo is None:
        # Treat naive input as UTC.
        ts_utc = ts_utc.replace(tzinfo=ZoneInfo("UTC"))

    tz = ZoneInfo(tz_name)
    local_ts = ts_utc.astimezone(tz)
    rt = _parse_reset_time(reset_time)
    local_reset = local_ts.replace(hour=rt.hour, minute=rt.minute, second=0, microsecond=0)
    if local_ts < local_reset:
        # Before reset boundary -> belongs to previous day.
        from datetime import timedelta

        local_day = (local_reset - timedelta(days=1)).date()
    else:
        local_day = local_reset.date()
    return local_day.isoformat()


def _decimal_from_float(x: float) -> Decimal:
    # Use str() rather than repr() to keep stable, human-scale precision.
    # This is deterministic as long as input floats are deterministic.
    return Decimal(str(float(x)))


def stable_required_slices(entry_risk_pct: float, slice_pct: float) -> int:
    if slice_pct <= 0:
        return 0
    if entry_risk_pct <= 0:
        return 0

    # Quantize to avoid float boundary noise (e.g. 0.005000000000000001).
    e = _decimal_from_float(entry_risk_pct).quantize(Decimal("0.000000000001"))
    s = _decimal_from_float(slice_pct).quantize(Decimal("0.000000000001"))
    raw = (e / s) if s != 0 else Decimal("0")

    # ROUND_CEILING is deterministic for Decimal.
    return int(raw.to_integral_value(rounding=ROUND_CEILING))


class DailyRiskBudgetSlices:
    """Append-only, restart-safe daily slice budgeting.

    Scope: per account_id (or sleeve) per run directory (ledger file).
    """

    def __init__(self, policy: RiskBudgetPolicy, *, run_dir: Optional[Any] = None, fail_closed: bool = False):
        self.policy = policy
        self.state = RiskBudgetState(campaign_slices_remaining=int(policy.total_slices_per_campaign))
        self._fail_closed = bool(fail_closed)
        self._run_dir = run_dir
        self._lock: Optional[_ProcessFileLock] = None

        self._trusted: bool = True
        self._untrusted_reason: str | None = None
        self._untrusted_detail: str | None = None
        self._trust_failure_audited: bool = False

        if self._fail_closed and run_dir is None:
            self._mark_untrusted("RUN_DIR_MISSING", detail="run_dir is required for strict budget enforcement")

        if run_dir is not None:
            try:
                base = Path(run_dir)
                base.mkdir(parents=True, exist_ok=True)
                self._lock = _ProcessFileLock(base / f"risk_budget.{policy.policy_version}.lock")
            except Exception:
                self._lock = None
                if self._fail_closed:
                    self._mark_untrusted("LOCK_INIT_FAILURE", detail="failed to initialize process lock")

    def is_trusted(self) -> bool:
        return bool(self._trusted)

    def untrusted_info(self) -> dict[str, Any]:
        return {
            "trusted": bool(self._trusted),
            "reason": self._untrusted_reason,
            "detail": self._untrusted_detail,
            "policy_version": self.policy.policy_version,
        }

    def audit_trust_failure(self, ledger: Any, *, account_id: str) -> None:
        if self._trusted:
            return
        if self._trust_failure_audited:
            return
        self._trust_failure_audited = True
        self._append_ledger(
            ledger,
            {
                "type": "RISK_BUDGET_TRUST_FAILURE",
                "account_id": account_id,
                "policy_version": self.policy.policy_version,
                "fail_closed": bool(self._fail_closed),
                "reason": self._untrusted_reason,
                "detail": self._untrusted_detail,
            },
        )

    def _mark_untrusted(self, reason: str, *, detail: str | None = None) -> None:
        if not self._trusted:
            return
        self._trusted = False
        self._untrusted_reason = str(reason)
        self._untrusted_detail = str(detail) if detail is not None else None

    def rehydrate_from_ledger(self, ledger: Any, *, account_id: str) -> None:
        """Rebuild state from existing audit.jsonl.

        Note: this is O(N) once at startup; per-decision checks stay O(1).
        """
        path = getattr(ledger, "path", None)
        if path is None or not getattr(path, "exists", lambda: False)():
            return

        self.state = RiskBudgetState(campaign_slices_remaining=int(self.policy.total_slices_per_campaign))
        try:
            with open(path, "r") as f:
                for line in f:
                    try:
                        rec = json.loads(line)
                    except Exception:
                        continue

                    if rec.get("type") == "RISK_BUDGET_DAY_RESET" and rec.get("account_id") == account_id:
                        self.state.day_key = rec.get("day_key")
                        self.state.e_ref = float(rec.get("e_ref") or 0.0)
                        self.state.entries_today = 0
                        self.state.slices_used_today = 0
                        continue

                    if rec.get("type") == "RISK_BUDGET_ENTRY_DECISION" and rec.get("account_id") == account_id:
                        key = str(rec.get("idempotency_key") or "")
                        if key and key in self.state.spent_keys:
                            continue

                        if key:
                            self.state.spent_keys.add(key)
                            self.state.prior_decisions[key] = {
                                "allow": rec.get("decision") == "ALLOW",
                                "reason_code": rec.get("reason_code"),
                                "required_slices": int(rec.get("required_slices") or 0),
                                "entry_risk_pct": float(rec.get("entry_risk_pct") or 0.0),
                                "day_key": rec.get("day_key"),
                                "e_ref": float(rec.get("e_ref") or 0.0),
                                "campaign_slices_remaining": int(rec.get("campaign_slices_remaining_after") or self.state.campaign_slices_remaining),
                                "entries_today": int(rec.get("entries_today_after") or self.state.entries_today),
                                "slices_used_today": int(rec.get("slices_used_today_after") or self.state.slices_used_today),
                            }

                        # Replay mutations (ALLOW only)
                        if rec.get("decision") != "ALLOW":
                            continue

                        day_key = rec.get("day_key")
                        if day_key and self.state.day_key != day_key:
                            self.state.day_key = day_key
                            self.state.entries_today = 0
                            self.state.slices_used_today = 0
                        self.state.campaign_slices_remaining = int(rec.get("campaign_slices_remaining_after") or self.state.campaign_slices_remaining)
                        self.state.entries_today = int(rec.get("entries_today_after") or self.state.entries_today)
                        self.state.slices_used_today = int(rec.get("slices_used_today_after") or self.state.slices_used_today)
        except Exception as e:
            self._mark_untrusted("REHYDRATE_FAILURE", detail=str(e))
            if self._fail_closed:
                raise
            logger.warning("Risk budget rehydrate failed: %s", e)

    def _ensure_day(self, *, ts_utc: datetime, account_id: str, e_ref: float, ledger: Optional[Any]) -> tuple[str, float]:
        day_key = compute_day_key(ts_utc, self.policy.risk_reset_tz, self.policy.risk_reset_time)

        if self.state.day_key == day_key and self.state.e_ref is not None:
            return day_key, float(self.state.e_ref)

        # Day reset (first decision for this day).
        self.state.day_key = day_key
        self.state.e_ref = float(e_ref)
        self.state.entries_today = 0
        self.state.slices_used_today = 0

        if ledger is not None:
            self._append_ledger(
                ledger,
                {
                    "type": "RISK_BUDGET_DAY_RESET",
                    "account_id": account_id,
                    "day_key": day_key,
                    "e_ref": float(e_ref),
                    "campaign_slices_remaining": int(self.state.campaign_slices_remaining),
                    "policy_version": self.policy.policy_version,
                    "policy": {
                        "total_slices_per_campaign": self.policy.total_slices_per_campaign,
                        "slice_pct": self.policy.slice_pct,
                        "max_entries_per_day": self.policy.max_entries_per_day,
                        "max_slices_per_day": self.policy.max_slices_per_day,
                        "max_slices_per_entry": self.policy.max_slices_per_entry,
                        "risk_reset_tz": self.policy.risk_reset_tz,
                        "risk_reset_time": self.policy.risk_reset_time,
                    },
                },
            )

        return day_key, float(e_ref)

    def evaluate_entry(
        self,
        intent: EntryIntent,
        *,
        e_ref: float,
        ledger: Optional[Any] = None,
    ) -> EntryDecision:
        ts_utc = intent.ts_utc or datetime.now(timezone.utc)

        if self._fail_closed and (self._lock is None or not self._trusted):
            if self._lock is None and self._trusted:
                self._mark_untrusted("LOCK_UNAVAILABLE", detail="lock is required for strict budget enforcement")

            day_key = compute_day_key(ts_utc, self.policy.risk_reset_tz, self.policy.risk_reset_time)
            if ledger is not None:
                self._append_ledger(
                    ledger,
                    {
                        "type": "RISK_BUDGET_SYSTEM_BLOCK",
                        "account_id": intent.account_id,
                        "day_key": day_key,
                        "symbol": intent.symbol,
                        "side": intent.side,
                        "idempotency_key": intent.idempotency_key(),
                        "reason_code": "STATE_UNTRUSTED",
                        "system": self.untrusted_info(),
                    },
                )

            return EntryDecision(
                allow=False,
                reason_code="STATE_UNTRUSTED",
                entry_risk_pct=0.0,
                required_slices=0,
                day_key=day_key,
                e_ref=float(e_ref),
                campaign_slices_remaining=int(self.state.campaign_slices_remaining),
                entries_today=int(self.state.entries_today),
                slices_used_today=int(self.state.slices_used_today),
            )
        day_key = compute_day_key(ts_utc, self.policy.risk_reset_tz, self.policy.risk_reset_time)
        id_key = intent.idempotency_key()

        def emit_early_block(reason_code: ReasonCode) -> EntryDecision:
            decision = EntryDecision(
                allow=False,
                reason_code=reason_code,
                entry_risk_pct=0.0,
                required_slices=0,
                day_key=day_key,
                e_ref=float(e_ref),
                campaign_slices_remaining=int(self.state.campaign_slices_remaining),
                entries_today=int(self.state.entries_today),
                slices_used_today=int(self.state.slices_used_today),
            )

            if ledger is not None:
                lock_cm = self._lock if self._lock is not None else _NullLock()
                with lock_cm:
                    pre = {
                        "campaign_slices_remaining": int(self.state.campaign_slices_remaining),
                        "entries_today": int(self.state.entries_today),
                        "slices_used_today": int(self.state.slices_used_today),
                    }
                    self._append_entry_decision_record(
                        ledger,
                        intent,
                        day_key=day_key,
                        frozen_e_ref=float(e_ref),
                        entry_risk_pct=0.0,
                        required_slices=0,
                        allow=False,
                        reason_code=reason_code,
                        id_key=id_key,
                        pre=pre,
                        post=pre,
                    )

            return decision

        if e_ref <= 0:
            return emit_early_block("INVALID_E_REF")

        if intent.stop_loss_price is None:
            return emit_early_block("MISSING_STOP")

        if intent.expected_entry_price <= 0 or intent.stop_loss_price <= 0 or intent.quantity <= 0:
            return emit_early_block("INVALID_PRICES")

        # Atomic section: check + decrement + ledger append.
        lock_cm = self._lock if self._lock is not None else _NullLock()
        with lock_cm as lock_obj:
            if self._fail_closed and isinstance(lock_obj, _ProcessFileLock) and not lock_obj.acquired:
                self._mark_untrusted("LOCK_ACQUIRE_FAILURE", detail="failed to acquire process lock")
                day_key = compute_day_key(ts_utc, self.policy.risk_reset_tz, self.policy.risk_reset_time)
                if ledger is not None:
                    self._append_ledger(
                        ledger,
                        {
                            "type": "RISK_BUDGET_SYSTEM_BLOCK",
                            "account_id": intent.account_id,
                            "day_key": day_key,
                            "symbol": intent.symbol,
                            "side": intent.side,
                            "idempotency_key": intent.idempotency_key(),
                            "reason_code": "STATE_UNTRUSTED",
                            "system": self.untrusted_info(),
                        },
                    )
                return EntryDecision(
                    allow=False,
                    reason_code="STATE_UNTRUSTED",
                    entry_risk_pct=0.0,
                    required_slices=0,
                    day_key=day_key,
                    e_ref=float(e_ref),
                    campaign_slices_remaining=int(self.state.campaign_slices_remaining),
                    entries_today=int(self.state.entries_today),
                    slices_used_today=int(self.state.slices_used_today),
                )

            day_key, frozen_e_ref = self._ensure_day(ts_utc=ts_utc, account_id=intent.account_id, e_ref=e_ref, ledger=ledger)

            if id_key in self.state.spent_keys:
                prior = self.state.prior_decisions.get(id_key) or {}
                return EntryDecision(
                    allow=bool(prior.get("allow", False)),
                    reason_code=prior.get("reason_code") or "OK",
                    entry_risk_pct=float(prior.get("entry_risk_pct") or 0.0),
                    required_slices=int(prior.get("required_slices") or 0),
                    day_key=str(prior.get("day_key") or day_key),
                    e_ref=float(prior.get("e_ref") or frozen_e_ref),
                    campaign_slices_remaining=int(prior.get("campaign_slices_remaining") or self.state.campaign_slices_remaining),
                    entries_today=int(prior.get("entries_today") or self.state.entries_today),
                    slices_used_today=int(prior.get("slices_used_today") or self.state.slices_used_today),
                )

            max_loss_to_stop = abs(float(intent.expected_entry_price) - float(intent.stop_loss_price)) * float(intent.quantity)
            entry_risk_pct = max_loss_to_stop / float(frozen_e_ref) if frozen_e_ref > 0 else 0.0
            required_slices = stable_required_slices(entry_risk_pct, float(self.policy.slice_pct))

            reason: ReasonCode = "OK"
            allow = True

            if required_slices > int(self.policy.max_slices_per_entry):
                allow = False
                reason = "ENTRY_TOO_LARGE_FOR_DAILY_CAP"
            elif self.state.entries_today + 1 > int(self.policy.max_entries_per_day):
                allow = False
                reason = "DAILY_ENTRIES_EXCEEDED"
            elif self.state.slices_used_today + required_slices > int(self.policy.max_slices_per_day):
                allow = False
                reason = "DAILY_SLICES_EXCEEDED"
            elif self.state.campaign_slices_remaining - required_slices < 0:
                allow = False
                reason = "CAMPAIGN_SLICES_EXCEEDED"

            pre = {
                "campaign_slices_remaining": int(self.state.campaign_slices_remaining),
                "entries_today": int(self.state.entries_today),
                "slices_used_today": int(self.state.slices_used_today),
            }

            if allow:
                self.state.campaign_slices_remaining -= int(required_slices)
                self.state.entries_today += 1
                self.state.slices_used_today += int(required_slices)

            post = {
                "campaign_slices_remaining": int(self.state.campaign_slices_remaining),
                "entries_today": int(self.state.entries_today),
                "slices_used_today": int(self.state.slices_used_today),
            }

            # Track idempotency for both ALLOW and BLOCK to guarantee retry stability.
            self.state.spent_keys.add(id_key)
            self.state.prior_decisions[id_key] = {
                "allow": allow,
                "reason_code": reason,
                "required_slices": int(required_slices),
                "entry_risk_pct": float(entry_risk_pct),
                "day_key": day_key,
                "e_ref": float(frozen_e_ref),
                "campaign_slices_remaining": post["campaign_slices_remaining"],
                "entries_today": post["entries_today"],
                "slices_used_today": post["slices_used_today"],
            }

            if ledger is not None:
                self._append_entry_decision_record(
                    ledger,
                    intent,
                    day_key=day_key,
                    frozen_e_ref=float(frozen_e_ref),
                    entry_risk_pct=float(entry_risk_pct),
                    required_slices=int(required_slices),
                    allow=allow,
                    reason_code=reason,
                    id_key=id_key,
                    pre=pre,
                    post=post,
                )

            return EntryDecision(
                allow=allow,
                reason_code=reason,
                entry_risk_pct=float(entry_risk_pct),
                required_slices=int(required_slices),
                day_key=day_key,
                e_ref=float(frozen_e_ref),
                campaign_slices_remaining=int(self.state.campaign_slices_remaining),
                entries_today=int(self.state.entries_today),
                slices_used_today=int(self.state.slices_used_today),
            )

    def _append_entry_decision_record(
        self,
        ledger: Any,
        intent: EntryIntent,
        *,
        day_key: str,
        frozen_e_ref: float,
        entry_risk_pct: float,
        required_slices: int,
        allow: bool,
        reason_code: ReasonCode,
        id_key: str,
        pre: dict[str, int],
        post: dict[str, int],
    ) -> None:
        self._append_ledger(
            ledger,
            {
                "type": "RISK_BUDGET_ENTRY_DECISION",
                "account_id": intent.account_id,
                "day_key": day_key,
                "symbol": intent.symbol,
                "side": intent.side,
                "quantity": float(intent.quantity),
                "expected_entry_price": float(intent.expected_entry_price),
                "stop_loss_price": float(intent.stop_loss_price) if intent.stop_loss_price is not None else None,
                "e_ref": float(frozen_e_ref),
                "entry_risk_pct": float(entry_risk_pct),
                "required_slices": int(required_slices),
                "decision": "ALLOW" if allow else "BLOCK",
                "reason_code": reason_code,
                "idempotency_key": id_key,
                "campaign_slices_remaining_before": int(pre["campaign_slices_remaining"]),
                "entries_today_before": int(pre["entries_today"]),
                "slices_used_today_before": int(pre["slices_used_today"]),
                "campaign_slices_remaining_after": int(post["campaign_slices_remaining"]),
                "entries_today_after": int(post["entries_today"]),
                "slices_used_today_after": int(post["slices_used_today"]),
                "policy_version": self.policy.policy_version,
            },
        )

    def _append_ledger(self, ledger: Any, record: dict[str, Any]) -> None:
        # AuditLedger has a private _append we rely on elsewhere in the repo.
        append = getattr(ledger, "_append", None)
        if callable(append):
            append(record)
            return

        # Fall back to writing a raw record without chaining.
        path = getattr(ledger, "path", None)
        if path is None:
            return
        try:
            with open(path, "a") as f:
                f.write(json.dumps(record) + "\n")
        except Exception:
            return


class _NullLock:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class _ProcessFileLock:
    """Best-effort cross-process lock using fcntl on Unix.

    On non-Unix platforms, this becomes a no-op lock.
    """

    def __init__(self, path: Path):
        self._path = Path(path)
        self._fh = None
        self.acquired = False

    def __enter__(self):
        self.acquired = False
        try:
            import fcntl  # Unix only

            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._fh = open(self._path, "a+")
            fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX)
            self.acquired = True
        except Exception:
            self._fh = None
            self.acquired = False
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            import fcntl

            if self._fh is not None:
                fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
                self._fh.close()
        except Exception:
            pass
        finally:
            self._fh = None
            self.acquired = False
        return False
