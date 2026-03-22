from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.core.time_filter.market_hours import (
    TradingSession,
    get_active_sessions,
    get_primary_session,
    minutes_to_next_funding,
    normalize_dt_to_utc,
)

logger = logging.getLogger("time_filter")

# 기본값 (config 없을 때 사용)
_DEFAULT_TRADE_SESSIONS = ("SEOUL", "LONDON", "NY", "OVERLAP")
_DEFAULT_ENTRY_SCORE_MIN = 70  # [초기값]
_DEFAULT_ENTRY_SCORE_HIGH_RISK_MIN = 80  # [초기값]


class SessionFilter:
    """
    세션 기반 거래 허용 여부 판정 엔진.

    설계 원칙:
    - config 없이도 인스턴스화 가능 (기본값 사용)
    - check(dt_utc) → dict (명세 정의 key 준수, 변경 금지)
    - weekday/weekend 분기 로직 없음
    - dt.weekday() 호출 없음
    """

    def __init__(self, config: Optional[Any] = None) -> None:
        self._config = config
        logger.info("time_filter session_filter initialized")

    def _trade_sessions(self) -> List[str]:
        if self._config is not None:
            sessions = getattr(self._config, "trade_sessions", None)
            if sessions is not None:
                return list(sessions)
        return list(_DEFAULT_TRADE_SESSIONS)

    def _entry_score_min(self) -> int:
        if self._config is not None:
            v = getattr(self._config, "entry_score_min", None)
            if v is not None:
                return int(v)
        return _DEFAULT_ENTRY_SCORE_MIN

    def _entry_score_high_risk_min(self) -> int:
        if self._config is not None:
            v = getattr(self._config, "entry_score_high_risk_min", None)
            if v is not None:
                return int(v)
        return _DEFAULT_ENTRY_SCORE_HIGH_RISK_MIN

    # ── 핵심 메서드 ────────────────────────────────────────────

    def check(self, dt_utc: Optional[datetime] = None) -> Dict[str, Any]:
        """
        반환 dict (key 절대 변경 금지):
          allowed, primary_session, active_sessions, reason, checked_ts_utc
        """
        if dt_utc is None:
            dt_utc = datetime.now(timezone.utc)
        utc_dt = normalize_dt_to_utc(dt_utc)

        active_enum = get_active_sessions(utc_dt)
        primary_enum = get_primary_session(active_enum)
        active_names = [s.value for s in active_enum]
        allowed_sessions = self._trade_sessions()

        if primary_enum is TradingSession.CLOSED:
            allowed = False
        else:
            allowed = primary_enum.value in allowed_sessions

        reason = "allowed_session" if allowed else "outside_allowed_session"

        result: Dict[str, Any] = {
            "allowed": allowed,
            "primary_session": primary_enum.value,
            "active_sessions": active_names,
            "reason": reason,
            "checked_ts_utc": utc_dt.isoformat(),
        }
        return result

    def is_allowed(self, dt_utc: Optional[datetime] = None) -> bool:
        return self.check(dt_utc)["allowed"]

    def get_primary_session(self, dt_utc: Optional[datetime] = None) -> str:
        return self.check(dt_utc)["primary_session"]

    def get_effective_entry_score_min(self, dt_utc: Optional[datetime] = None) -> int:
        """
        SEOUL 세션 → entry_score_high_risk_min (80) 적용.
        그 외 세션  → entry_score_min (70) 적용.
        """
        primary = self.get_primary_session(dt_utc)
        if primary == TradingSession.SEOUL.value:
            return self._entry_score_high_risk_min()
        return self._entry_score_min()

    def minutes_to_next_funding(self, dt_utc: Optional[datetime] = None) -> float:
        if dt_utc is None:
            dt_utc = datetime.now(timezone.utc)
        return minutes_to_next_funding(dt_utc)

    # ── 기존 코드 호환 메서드 ──────────────────────────────────

    def evaluate(self, dt: Optional[datetime] = None):
        """
        기존 모듈 호환용. check() 결과를 SessionFilterResult로 래핑.
        """
        from dataclasses import dataclass

        @dataclass
        class SessionFilterResult:
            allowed: bool
            primary_session: str
            active_sessions: list
            reason: str
            checked_ts_utc: str

        r = self.check(dt)
        return SessionFilterResult(**r)

    def is_trading_session_allowed(self, dt: Optional[datetime] = None) -> bool:
        """기존 코드 호환 alias."""
        return self.is_allowed(dt)

