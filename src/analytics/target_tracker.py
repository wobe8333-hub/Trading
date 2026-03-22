from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("analytics.target_tracker")

_WIN_RATE_WARNING = 0.52  # [검증값]
_MAX_DAYS_WARNING = 180   # [검증값] 6개월


class TargetTracker:
    """
    $700 → $10,000 달성 추적기.

    compute() 반환 dict:
    current_equity, remaining_amount, elapsed_days,
    daily_avg_pnl, estimated_completion_days,
    estimated_completion_date, current_win_rate_20,
    current_rr_20, is_on_track, warning
    """

    def compute(
        self,
        current_equity: float,
        start_equity: float,
        target_equity: float,
        trade_history: List[Dict[str, Any]],
        elapsed_days: float,
    ) -> Dict[str, Any]:
        try:
            return self._compute(
                current_equity, start_equity, target_equity,
                trade_history, elapsed_days,
            )
        except Exception as exc:
            logger.error("target_tracker compute failed error=%s", exc)
            return self._default_result(current_equity, target_equity)

    def _compute(
        self,
        current_equity: float,
        start_equity: float,
        target_equity: float,
        trade_history: List[Dict[str, Any]],
        elapsed_days: float,
    ) -> Dict[str, Any]:
        remaining = max(0.0, target_equity - current_equity)

        daily_avg = (
            (current_equity - start_equity) / elapsed_days
            if elapsed_days > 0 else 0.0
        )

        est_days = remaining / daily_avg if daily_avg > 1e-9 else float("inf")
        est_days = min(est_days, 9999.0)

        est_date = (
            (datetime.now(timezone.utc) + timedelta(days=est_days)).strftime("%Y-%m-%d")
            if est_days < 9999.0 else "N/A"
        )

        last20 = trade_history[-20:] if trade_history else []
        win_rate_20 = (
            sum(1 for t in last20 if t.get("pnl_net", 0) > 0) / len(last20)
            if last20 else 0.0
        )
        rrs = [t.get("r_multiple", 0.0) for t in last20]
        avg_rr_20 = sum(rrs) / len(rrs) if rrs else 0.0

        is_on_track = remaining <= 0 or (daily_avg > 0 and est_days <= _MAX_DAYS_WARNING)

        warning: Optional[str] = None
        if last20 and win_rate_20 < _WIN_RATE_WARNING:
            warning = f"현재 승률 {win_rate_20:.1%} → 6개월 내 달성 불확실"
        elif est_days > _MAX_DAYS_WARNING:
            warning = "현재 추세 유지 시 6개월 초과 예상"

        return {
            "current_equity": round(current_equity, 2),
            "remaining_amount": round(remaining, 2),
            "elapsed_days": round(elapsed_days, 2),
            "daily_avg_pnl": round(daily_avg, 4),
            "estimated_completion_days": round(est_days, 2),
            "estimated_completion_date": est_date,
            "current_win_rate_20": round(win_rate_20, 4),
            "current_rr_20": round(avg_rr_20, 4),
            "is_on_track": is_on_track,
            "warning": warning,
        }

    @staticmethod
    def _default_result(current: float, target: float) -> Dict[str, Any]:
        return {
            "current_equity": current,
            "remaining_amount": max(0.0, target - current),
            "elapsed_days": 0.0,
            "daily_avg_pnl": 0.0,
            "estimated_completion_days": 9999.0,
            "estimated_completion_date": "N/A",
            "current_win_rate_20": 0.0,
            "current_rr_20": 0.0,
            "is_on_track": False,
            "warning": None,
        }

