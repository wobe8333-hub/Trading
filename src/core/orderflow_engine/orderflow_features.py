from __future__ import annotations

import logging
import math
from typing import Any, Dict, List

logger = logging.getLogger("orderflow.features")


def _safe(val: Any, default: float = 0.0) -> float:
    try:
        v = float(val)
        return v if math.isfinite(v) else default
    except (TypeError, ValueError):
        return default


def _compute_atr_last(klines: List[Dict[str, Any]], period: int = 14) -> float:
    """ATR 마지막값 반환. 데이터 부족 시 0.0."""
    if len(klines) < 2:
        return 0.0
    trs: List[float] = []
    for i in range(1, len(klines)):
        h = _safe(klines[i].get("high"))
        l = _safe(klines[i].get("low"))
        pc = _safe(klines[i - 1].get("close"))
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    if not trs:
        return 0.0
    alpha = 1.0 / period
    atr = trs[0]
    for tr in trs[1:]:
        atr = atr * (1 - alpha) + tr * alpha
    return atr


class OrderflowFeatureCalculator:
    """
    market_state → Orderflow 파생 지표 계산.
    """

    def compute(
        self, symbol: str, market_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        try:
            return self._compute(symbol, market_state)
        except Exception as exc:
            logger.error(
                "orderflow_features compute failed symbol=%s error=%s",
                symbol, exc,
            )
            return self._default_features()

    def _compute(
        self, symbol: str, market_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        # ── OI 변화율 ─────────────────────────────────────────
        oi_now = _safe(market_state.get("open_interest"), 1.0)
        oi_prev_5m = _safe(market_state.get("oi_prev_5m"), oi_now)

        oi_change_5m_pct = (
            (oi_now - oi_prev_5m) / oi_prev_5m
            if oi_prev_5m > 1e-9 else 0.0
        )
        # 1분 OI는 5분 OI의 1/5 근사
        oi_change_1m_pct = oi_change_5m_pct / 5.0

        # ── Volume Spike Ratio ────────────────────────────────
        klines_1m: List[Dict[str, Any]] = market_state.get("klines_1m") or []
        volumes = [_safe(k.get("volume")) for k in klines_1m]
        volume_spike_ratio = 1.0
        if len(volumes) >= 21:
            avg_vol = sum(volumes[-21:-1]) / 20
            if avg_vol > 0:
                volume_spike_ratio = volumes[-1] / avg_vol

        # ── Price Impulse (최근 1봉 가격 변화 / ATR) ──────────
        klines_3m: List[Dict[str, Any]] = market_state.get("klines_3m") or []
        atr = _compute_atr_last(klines_3m, period=14)
        price_impulse_atr = 0.0
        if len(klines_3m) >= 2 and atr > 1e-9:
            c_now = _safe(klines_3m[-1].get("close"))
            c_prev = _safe(klines_3m[-2].get("close"))
            price_impulse_atr = (c_now - c_prev) / atr

        # ── Bid/Ask Depth 변화율 ──────────────────────────────
        _ = _safe(market_state.get("orderbook_bid_depth"))
        _ = _safe(market_state.get("orderbook_ask_depth"))
        # 이전값이 없으면 0%로 처리 (향후 상태 저장 시 확장)
        bid_depth_change_pct = 0.0
        ask_depth_change_pct = 0.0

        # ── Trade Velocity ────────────────────────────────────
        recent_trades: List[Dict[str, Any]] = market_state.get("recent_trades") or []
        trade_velocity = float(len(recent_trades))

        # ── Absorption Signal ─────────────────────────────────
        # ask_depth가 50% 이상 증가했으나 가격이 유지 → 매수 흡수
        absorption_signal = (
            ask_depth_change_pct > 0.5
            and price_impulse_atr > -0.3
        )

        logger.info(
            "orderflow_features symbol=%s "
            "oi_chg_1m=%.6f oi_chg_5m=%.6f "
            "vol_spike=%.4f price_impulse=%.4f "
            "trade_vel=%.0f absorption=%s",
            symbol,
            oi_change_1m_pct, oi_change_5m_pct,
            volume_spike_ratio, price_impulse_atr,
            trade_velocity, absorption_signal,
        )
        return {
            "oi_change_1m_pct":    round(oi_change_1m_pct, 6),
            "oi_change_5m_pct":    round(oi_change_5m_pct, 6),
            "volume_spike_ratio":  round(volume_spike_ratio, 6),
            "price_impulse_atr":   round(price_impulse_atr, 6),
            "bid_depth_change_pct": round(bid_depth_change_pct, 6),
            "ask_depth_change_pct": round(ask_depth_change_pct, 6),
            "trade_velocity":      trade_velocity,
            "absorption_signal":   absorption_signal,
        }

    @staticmethod
    def _default_features() -> Dict[str, Any]:
        return {
            "oi_change_1m_pct":    0.0,
            "oi_change_5m_pct":    0.0,
            "volume_spike_ratio":  1.0,
            "price_impulse_atr":   0.0,
            "bid_depth_change_pct": 0.0,
            "ask_depth_change_pct": 0.0,
            "trade_velocity":      0.0,
            "absorption_signal":   False,
        }
