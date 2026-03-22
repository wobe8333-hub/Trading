from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import Tuple

from src.core.time_filter.market_hours import FUNDING_TIMES_UTC

logger = logging.getLogger("cost_guard.funding_time")

_FUNDING_BUFFER_MIN      = 15    # [초기값] 펀딩 정산 N분 전 차단
_POST_FUNDING_WINDOW_MIN = 5     # [초기값] 정산 후 N분 이내 반전 허용
_EXTREME_RATE_THRESHOLD  = 0.001 # [초기값] 극단 펀딩비 기준 (0.10%)
_POST_SCORE_MIN          = 80    # [초기값] 정산 후 반전 진입 최소 Entry Score


def _minutes_to_next_funding(now_utc: datetime) -> float:
    """다음 펀딩 정산까지 남은 분 수. 항상 양수."""
    current = now_utc.hour * 60 + now_utc.minute
    diffs   = []
    for h, m in FUNDING_TIMES_UTC:
        target = h * 60 + m
        diff   = target - current
        if diff <= 0:
            diff += 1440
        diffs.append(diff)
    return float(min(diffs))


def _minutes_since_last_funding(now_utc: datetime) -> float:
    """마지막 펀딩 정산 이후 경과 분 수."""
    return 480.0 - _minutes_to_next_funding(now_utc)  # 8시간 주기


class FundingTimeGuard:
    """
    펀딩 정산 시각 전후 진입 제어.

    is_entry_allowed():
      - 정산 N분 전 차단 (default: 15분)
      - 차단 예외: 정산 후 5분 이내 + 극단 funding_rate + Entry Score 80+

    is_post_funding_reversal_allowed():
      - 정산 직후 반전 기회 진입 허용 여부
    """

    def is_entry_allowed(
        self,
        now_utc: datetime,
    ) -> Tuple[bool, str]:
        """
        반환: (True, "정상") / (False, "펀딩 정산 N.N분 전")
        예외 발생 시 (True, "guard_error") 반환.
        """
        try:
            return self._check(now_utc)
        except Exception as exc:
            logger.error("funding_time_guard failed error=%s", exc)
            return True, "guard_error"

    def _check(self, now_utc: datetime) -> Tuple[bool, str]:
        utc = now_utc.replace(tzinfo=timezone.utc) if now_utc.tzinfo is None else now_utc
        minutes_to = _minutes_to_next_funding(utc)

        if minutes_to <= _FUNDING_BUFFER_MIN:  # [초기값] 15분
            reason = f"펀딩 정산 {minutes_to:.1f}분 전"
            logger.info("funding_time_guard blocked reason=%s", reason)
            return False, reason

        return True, "정상"

    @staticmethod
    def is_post_funding_reversal_allowed(
        now_utc: datetime,
        funding_rate: float,
        entry_score: int,
    ) -> bool:
        """
        구현지침서 명세:
          정산 후 5분 이내 + abs(funding_rate) >= 0.001 + entry_score >= 80
        """
        try:
            utc = now_utc.replace(tzinfo=timezone.utc) if now_utc.tzinfo is None else now_utc
            minutes_since = _minutes_since_last_funding(utc)
            is_extreme    = abs(funding_rate) >= _EXTREME_RATE_THRESHOLD  # [초기값]
            return (
                minutes_since <= _POST_FUNDING_WINDOW_MIN   # [초기값] 5분
                and is_extreme
                and entry_score >= _POST_SCORE_MIN           # [초기값] 80
            )
        except Exception as exc:
            logger.error("post_funding_reversal_check failed error=%s", exc)
            return False

