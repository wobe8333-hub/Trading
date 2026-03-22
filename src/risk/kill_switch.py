from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional

logger = logging.getLogger("risk.kill_switch")

# 수동 해제만 가능한 조건들
_MANUAL_ONLY_REASONS = frozenset(
    [
        "STOP_NOT_REGISTERED",
        "API_ERROR",
        "INCONSISTENCY",
    ]
)

# 발동 조건별 쿨다운 (시간 단위, -1=수동해제)
_COOLDOWN_MAP: Dict[str, float] = {
    "DAILY_LOSS_LIMIT": 0.0,  # [검증값] 다음날 자동
    "CONSECUTIVE_LOSSES": 1.0,  # [검증값] 1시간 쿨다운
    "STOP_NOT_REGISTERED": -1.0,  # [검증값] 수동 해제만
    "API_ERROR": -1.0,  # [검증값] 수동 해제만
    "SPREAD_ANOMALY": 0.0,  # [검증값] 자동 감시
    "SLIPPAGE_ANOMALY": 0.0,  # [검증값]
    "SAME_COIN_LOSS": 2.0,  # [검증값] symbol 차단 2시간
    "SAME_REGIME_LOSS": 1.0,  # [검증값] regime 차단 1시간
    "INCONSISTENCY": -1.0,  # [검증값] 수동 해제만
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class KillSwitch:
    """
    9개 조건에서 즉시 거래를 차단하는 최우선 안전 장치.

    발동 조건:
    DAILY_LOSS_LIMIT / CONSECUTIVE_LOSSES / STOP_NOT_REGISTERED
    API_ERROR / SPREAD_ANOMALY / SLIPPAGE_ANOMALY
    SAME_COIN_LOSS / SAME_REGIME_LOSS / INCONSISTENCY
    """

    def __init__(self) -> None:
        self.is_active: bool = False
        self.reason: str = ""
        self.cooldown_until: Optional[datetime] = None
        self.blocked_symbols: Dict[str, datetime] = {}
        self.blocked_regimes: Dict[str, datetime] = {}

    def trigger(self, reason: str, cooldown_hours: float = 0.0) -> None:
        """Kill Switch 발동. logs/kill_switch/ 에 즉시 기록."""
        self.is_active = True
        self.reason = reason

        hours = _COOLDOWN_MAP.get(reason, cooldown_hours)
        if hours > 0:
            self.cooldown_until = _utcnow() + timedelta(hours=hours)
        elif hours == 0.0:
            self.cooldown_until = None  # 조건 해소 시 자동 해제
        else:
            self.cooldown_until = None  # -1: 수동 해제만

        self._write_log(reason)
        logger.warning(
            "kill_switch TRIGGERED reason=%s cooldown_hours=%.1f", reason, hours
        )

    def is_blocked(self) -> bool:
        """차단 여부 반환. 쿨다운 경과 시 auto_release() 시도."""
        if not self.is_active:
            return False
        self.auto_release()
        return self.is_active

    def auto_release(self) -> bool:
        """쿨다운 경과 + 수동 해제 불필요 시 자동 해제."""
        if not self.is_active:
            return True
        if self.reason in _MANUAL_ONLY_REASONS:
            return False  # 수동 해제만
        if self.cooldown_until is None:
            return False  # 조건 감시 중
        if _utcnow() >= self.cooldown_until:
            self.is_active = False
            self.reason = ""
            self.cooldown_until = None
            logger.info("kill_switch AUTO_RELEASED")
            return True
        return False

    def manual_release(self) -> None:
        """수동 해제."""
        self.is_active = False
        self.reason = ""
        self.cooldown_until = None
        logger.info("kill_switch MANUAL_RELEASED")

    def block_symbol(self, symbol: str, hours: float) -> None:
        self.blocked_symbols[symbol] = _utcnow() + timedelta(hours=hours)
        logger.info(
            "kill_switch SYMBOL_BLOCKED symbol=%s hours=%.1f", symbol, hours
        )

    def is_symbol_blocked(self, symbol: str) -> bool:
        if symbol not in self.blocked_symbols:
            return False
        if _utcnow() >= self.blocked_symbols[symbol]:
            del self.blocked_symbols[symbol]
            return False
        return True

    def block_regime(self, regime: str, hours: float) -> None:
        self.blocked_regimes[regime] = _utcnow() + timedelta(hours=hours)
        logger.info(
            "kill_switch REGIME_BLOCKED regime=%s hours=%.1f", regime, hours
        )

    def is_regime_blocked(self, regime: str) -> bool:
        if regime not in self.blocked_regimes:
            return False
        if _utcnow() >= self.blocked_regimes[regime]:
            del self.blocked_regimes[regime]
            return False
        return True

    def _write_log(self, reason: str) -> None:
        try:
            os.makedirs("logs/kill_switch", exist_ok=True)
            ts = _utcnow().strftime("%Y%m%d_%H%M%S")
            path = f"logs/kill_switch/{ts}_{reason}.log"
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"timestamp={_utcnow().isoformat()}\nreason={reason}\n")
        except Exception as exc:
            logger.error("kill_switch log write failed error=%s", exc)

