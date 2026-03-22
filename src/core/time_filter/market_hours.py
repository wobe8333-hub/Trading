from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import List, Tuple, Union


class TradingSession(str, Enum):
    SEOUL   = "SEOUL"
    LONDON  = "LONDON"
    NY      = "NY"
    OVERLAP = "OVERLAP"
    CLOSED  = "CLOSED"


@dataclass(frozen=True)
class SessionWindow:
    name: TradingSession
    start_hour: int  # UTC 시작 시 (포함)
    start_min: int
    end_hour: int    # UTC 종료 시 (포함)
    end_min: int


# 세션 정의 — 절대 변경 금지
SESSION_WINDOWS: List[SessionWindow] = [
    SessionWindow(TradingSession.SEOUL,    0,  0,  5, 59),
    SessionWindow(TradingSession.LONDON,   8,  0, 16, 59),
    SessionWindow(TradingSession.NY,      13,  0, 21, 59),
    SessionWindow(TradingSession.OVERLAP, 13,  0, 16, 59),
]

# 펀딩 시각 (UTC) — 00:00 / 08:00 / 16:00
FUNDING_TIMES_UTC: List[Tuple[int, int]] = [(0, 0), (8, 0), (16, 0)]

# primary_session 우선순위 (인덱스 낮을수록 우선)
PRIMARY_PRIORITY: List[TradingSession] = [
    TradingSession.OVERLAP,
    TradingSession.NY,
    TradingSession.LONDON,
    TradingSession.SEOUL,
    TradingSession.CLOSED,
]


def normalize_dt_to_utc(dt: datetime) -> datetime:
    """naive datetime은 UTC로 간주, aware datetime은 UTC로 변환."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def is_in_session(dt_utc: datetime, window: SessionWindow) -> bool:
    """주말/평일 구분 없이 UTC 시간만으로 세션 포함 여부 판정."""
    t = (dt_utc.hour, dt_utc.minute)
    s = (window.start_hour, window.start_min)
    e = (window.end_hour, window.end_min)
    return s <= t <= e


def get_active_sessions(dt: datetime) -> List[TradingSession]:
    """
    활성 세션 목록 반환.
    없으면 [CLOSED] 반환.
    주말/평일 구분 없음.
    """
    utc_dt = normalize_dt_to_utc(dt)
    active = [w.name for w in SESSION_WINDOWS if is_in_session(utc_dt, w)]
    return active if active else [TradingSession.CLOSED]


def get_primary_session(dt_or_active: Union[datetime, List[TradingSession]]) -> TradingSession:
    """
    활성 세션 리스트 또는 datetime을 받아 primary session 반환.
    - list[TradingSession] 전달 시: PRIMARY_PRIORITY 기반 선택
    - datetime 전달 시: get_active_sessions 호출 후 선택
    """
    if isinstance(dt_or_active, datetime):
        active = get_active_sessions(dt_or_active)
    else:
        active = dt_or_active
    for s in PRIMARY_PRIORITY:
        if s in active:
            return s
    return TradingSession.CLOSED


def minutes_to_next_funding(dt_utc: datetime) -> float:
    """현재 UTC 시각 기준 다음 펀딩까지 남은 분 수. 항상 양수 반환."""
    utc_dt = normalize_dt_to_utc(dt_utc)
    current_minutes = utc_dt.hour * 60 + utc_dt.minute
    candidates: List[int] = []
    for h, m in FUNDING_TIMES_UTC:
        target = h * 60 + m
        diff = target - current_minutes
        if diff <= 0:
            diff += 1440
        candidates.append(diff)
    return float(min(candidates))

