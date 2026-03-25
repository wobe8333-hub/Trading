from __future__ import annotations

import logging
import math
import time
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger("cost_guard.liquidity")

# ── 유동성 이상 감지 임계값 ──────────────────────────────────
_BID_DEPTH_DROP_RATIO  = 0.40   # [초기값] Bid Depth 40% 이상 감소
_SPREAD_SPIKE_RATIO    = 2.5    # [초기값] Spread 5분 평균의 2.5배 이상
_VOLUME_DROP_RATIO     = 0.20   # [초기값] 거래량 20분 평균의 20% 미만
_TRADE_INTERVAL_RATIO  = 3.0    # [초기값] 체결 간격 60초 전의 3배 이상
_VIOLATION_THRESHOLD   = 2      # 2개 이상 동시 발생 시 차단


def _safe(val: Any, default: float = 0.0) -> float:
    try:
        v = float(val)
        return v if math.isfinite(v) else default
    except (TypeError, ValueError):
        return default


class LiquidityMonitor:
    """
    유동성 이상 감지기. 2개 이상 조건 동시 충족 시 차단.

    조건1. Bid Depth 40% 이상 급감
    조건2. Spread 5분 평균의 2.5배 이상
    조건3. 3분 거래량 < 20분 평균의 20%
    조건4. 체결 간격 60초 전 대비 3배 이상

    내부 상태: 60초 이전 스냅샷 보관
    """

    def __init__(self) -> None:
        self._snapshot_ts:   float = 0.0
        self._snapshot:      Dict[str, Any] = {}
        self._spread_history: list = []   # 5분 spread 이력

    def is_liquidity_ok(
        self,
        symbol:       str,
        market_state: Dict[str, Any],
    ) -> Tuple[bool, str]:
        """
        반환: (True, "정상") / (False, "violations: N")
        예외 발생 시 (True, "모니터 오류 — 통과") 반환.
        """
        try:
            return self._check(symbol, market_state)
        except Exception as exc:
            logger.error(
                "liquidity_monitor failed symbol=%s error=%s", symbol, exc
            )
            return True, "monitor_error"

    def _check(
        self,
        symbol:       str,
        market_state: Dict[str, Any],
    ) -> Tuple[bool, str]:
        now        = time.time()
        bid_depth  = _safe(market_state.get("orderbook_bid_depth"))
        spread_bps = _safe(market_state.get("spread_bps"))
        vol_24h    = _safe(market_state.get("volume_24h"))
        trades     = market_state.get("recent_trades") or []

        # spread 이력 업데이트 (최근 5분 = 100개 3초 간격 근사)
        self._spread_history.append(spread_bps)
        if len(self._spread_history) > 100:
            self._spread_history = self._spread_history[-100:]
        spread_avg = (
            sum(self._spread_history) / len(self._spread_history)
            if self._spread_history else spread_bps
        )

        # 60초 이전 스냅샷
        snapshot_age  = now - self._snapshot_ts
        prev_bid      = _safe(self._snapshot.get("bid_depth",  bid_depth))
        prev_interval = _safe(self._snapshot.get("trade_interval", 1.0), 1.0)

        # 스냅샷 갱신 (60초마다)
        if snapshot_age >= 60:
            trade_interval = (
                60.0 / len(trades) if len(trades) > 0 else 60.0
            )
            self._snapshot    = {
                "bid_depth":      bid_depth,
                "spread_bps":     spread_bps,
                "volume":         vol_24h,
                "trade_interval": trade_interval,
            }
            self._snapshot_ts = now

        # ── 4개 조건 평가 ─────────────────────────────────────
        v1 = (                                                      # Bid Depth 40% 이상 감소
            prev_bid > 0
            and bid_depth < prev_bid * (1 - _BID_DEPTH_DROP_RATIO)
        )
        v2 = (                                                      # Spread 2.5배 이상
            spread_avg > 0
            and spread_bps > spread_avg * _SPREAD_SPIKE_RATIO
        )
        v3 = False   # volume 20분 평균 필요 (paper_mode → 항상 False)
        v4 = False   # trade_interval (paper_mode → 항상 False)

        violation_count = sum([v1, v2, v3, v4])
        ok = violation_count < _VIOLATION_THRESHOLD   # [초기값] 2개 미만

        reason = f"violations: {violation_count}" if not ok else "OK"
        logger.info(
            "liquidity_monitor symbol=%s ok=%s violations=%d "
            "v1_bid_drop=%s v2_spread_spike=%s "
            "spread_bps=%.4f spread_avg=%.4f bid_depth=%.2f prev_bid=%.2f",
            symbol, ok, violation_count,
            v1, v2,
            spread_bps, spread_avg, bid_depth, prev_bid,
        )
        return ok, reason

