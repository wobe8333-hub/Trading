from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import Any, Dict, Tuple

from src.core.execution_cost_guard.cost_calculator import CostCalculator
from src.core.execution_cost_guard.liquidity_monitor import LiquidityMonitor
from src.core.execution_cost_guard.funding_time_guard import FundingTimeGuard

logger = logging.getLogger("cost_guard")


def _safe(val: Any, default: float = 0.0) -> float:
    try:
        v = float(val)
        return v if math.isfinite(v) else default
    except (TypeError, ValueError):
        return default


class ExecutionCostGuard:
    """
    진입 전 마지막 비용 검사 게이트.

    검사 순서 (구현지침서 명세):
    1. LiquidityMonitor.is_liquidity_ok()     → False 시 LIQUIDITY 차단
    2. FundingTimeGuard.is_entry_allowed()    → False + 반전 예외 미충족 시 FUNDING_TIME 차단
    3. CostCalculator.compute_total_cost_bps() → 비용 > TP1*20% 시 COST_EXCEED 차단

    check() 반환: (bool, dict)
      True  → (True,  {"reason": "PASS",         "cost_detail": {...}})
      False → (False, {"reason": "LIQUIDITY" / "FUNDING_TIME" / "COST_EXCEED",
                        "cost_detail": {...}, "detail": str})
    """

    def __init__(self) -> None:
        self._cost_calc       = CostCalculator()
        self._liq_monitor     = LiquidityMonitor()
        self._funding_guard   = FundingTimeGuard()

    def check(
        self,
        symbol:         str,
        order_type:     str,         # "MARKET" / "LIMIT"
        order_size_usd: float,
        tp1_price:      float,
        entry_price:    float,
        regime:         str,
        now_utc:        datetime,
        funding_rate:   float,
        entry_score:    int,
        market_state:   Dict[str, Any],
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        모든 비용/유동성/펀딩 조건 검사.
        예외 발생 시 (True, {"reason": "GUARD_ERROR"}) 반환 — 시스템 중단 없음.
        """
        try:
            return self._check(
                symbol, order_type, order_size_usd,
                tp1_price, entry_price, regime,
                now_utc, funding_rate, entry_score, market_state,
            )
        except Exception as exc:
            logger.error(
                "execution_cost_guard check failed symbol=%s error=%s",
                symbol, exc,
            )
            return True, {"reason": "GUARD_ERROR", "cost_detail": {}}

    def _check(
        self,
        symbol:         str,
        order_type:     str,
        order_size_usd: float,
        tp1_price:      float,
        entry_price:    float,
        regime:         str,
        now_utc:        datetime,
        funding_rate:   float,
        entry_score:    int,
        market_state:   Dict[str, Any],
    ) -> Tuple[bool, Dict[str, Any]]:

        # ── 1. 유동성 검사 ────────────────────────────────────
        liq_ok, liq_reason = self._liq_monitor.is_liquidity_ok(symbol, market_state)
        if not liq_ok:
            logger.info(
                "cost_guard BLOCKED reason=LIQUIDITY symbol=%s %s",
                symbol, liq_reason,
            )
            return False, {
                "reason":      "LIQUIDITY",
                "detail":      liq_reason,
                "cost_detail": {},
            }

        # ── 2. 펀딩 시각 검사 ─────────────────────────────────
        fund_ok, fund_reason = self._funding_guard.is_entry_allowed(now_utc)
        if not fund_ok:
            # 정산 후 반전 예외 허용 여부 체크
            reversal_allowed = FundingTimeGuard.is_post_funding_reversal_allowed(
                now_utc, funding_rate, entry_score
            )
            if not reversal_allowed:
                logger.info(
                    "cost_guard BLOCKED reason=FUNDING_TIME symbol=%s %s",
                    symbol, fund_reason,
                )
                return False, {
                    "reason":      "FUNDING_TIME",
                    "detail":      fund_reason,
                    "cost_detail": {},
                }

        # ── 3. 비용 검사 ──────────────────────────────────────
        cost_detail = self._cost_calc.compute_total_cost_bps(
            symbol, order_type, order_size_usd, market_state, regime
        )

        # TP1 거리(bps) 계산
        if entry_price > 0:
            tp1_distance_bps = abs(tp1_price - entry_price) / entry_price * 10000
        else:
            tp1_distance_bps = 0.0

        cost_ok = CostCalculator.is_cost_acceptable(
            cost_detail["total_cost_bps"], tp1_distance_bps
        )

        if not cost_ok:
            logger.info(
                "cost_guard BLOCKED reason=COST_EXCEED symbol=%s total=%.2fbps tp1=%.2fbps",
                symbol,
                cost_detail["total_cost_bps"],
                tp1_distance_bps,
            )
            return False, {
                "reason":           "COST_EXCEED",
                "total_cost_bps":   cost_detail["total_cost_bps"],
                "tp1_distance_bps": tp1_distance_bps,
                "cost_detail":      cost_detail,
            }

        logger.info(
            "cost_guard PASS symbol=%s total=%.2fbps tp1=%.2fbps",
            symbol,
            cost_detail["total_cost_bps"],
            tp1_distance_bps,
        )
        return True, {
            "reason":           "PASS",
            "total_cost_bps":   cost_detail["total_cost_bps"],
            "tp1_distance_bps": tp1_distance_bps,
            "cost_detail":      cost_detail,
        }

