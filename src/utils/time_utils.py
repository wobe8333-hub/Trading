from __future__ import annotations

from datetime import datetime, timezone


def now_utc() -> datetime:
    """현재 UTC datetime 반환."""
    return datetime.now(timezone.utc)


def to_utc(ts: float) -> datetime:
    """Unix timestamp → UTC datetime."""
    return datetime.fromtimestamp(ts, tz=timezone.utc)


def format_duration(seconds: float) -> str:
    """초 → '2h 35m 10s' 형식 문자열."""
    seconds = max(0.0, seconds)
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    if h > 0:
        return f"{h}h {m}m {s}s"
    if m > 0:
        return f"{m}m {s}s"
    return f"{s}s"

