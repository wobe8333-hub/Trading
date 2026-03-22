from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

import numpy as np

from src.strategy.strategy_library.base_strategy import BaseStrategy
from src.utils.math_utils import (
    compute_ema,
    compute_atr,
    compute_vwap,
    compute_fibonacci_retracement,
)

logger = logging.getLogger("strategy.trend_continuation")


class TrendContinuation(BaseStrategy):
    """
    Trend Continuation — 3레이어

    레이어 1: EMA 삼중 정렬 + 피보나치 조정 + ATR 유지
    레이어 2: OI 유지/증가 + 거래량 감소 (조정 중)
    레이어 3: EMA20 지지 재개 봉 + 거래량 확인
    """

    def generate_signal(self, symbol, market_state, orderflow_state, direction=None):
        try:
            return self._generate(symbol, market_state, orderflow_state, direction)
        except Exception as exc:
            logger.error(
                "trend_continuation failed symbol=%s error=%s",
                symbol,
                exc,
            )
            return False, self._null_hit()

    def _generate(self, symbol, market_state, orderflow_state, direction):
        klines = market_state.get("klines_3m") or []
        if len(klines) < 55:
            return False, self._null_hit()

        closes = [float(k.get("close", 0)) for k in klines]
        highs = [float(k.get("high", 0)) for k in klines]
        lows = [float(k.get("low", 0)) for k in klines]
        volumes = [float(k.get("volume", 0)) for k in klines]

        ema20 = compute_ema(closes, 20)
        ema50 = compute_ema(closes, 50)
        ema200 = compute_ema(closes, 200) if len(closes) >= 200 else []
        atrs = compute_atr(highs, lows, closes, 14)

        if not (ema20 and ema50 and atrs):
            return False, self._null_hit()

        atr_last = atrs[-1]
        atr_mean20 = float(np.mean(atrs[-20:])) if len(atrs) >= 20 else atr_last

        dirs = []
        if direction in (None, "LONG"):
            dirs.append("LONG")
        if direction in (None, "SHORT"):
            dirs.append("SHORT")

        for d in dirs:
            # ── 레이어 1 ──────────────────────────────────────
            if d == "LONG":
                ema_triple = ema20[-1] > ema50[-1] and (not ema200 or ema50[-1] > ema200[-1])
            else:
                ema_triple = ema20[-1] < ema50[-1] and (not ema200 or ema50[-1] < ema200[-1])

            swing_high = max(highs[-20:])
            swing_low = min(lows[-20:])
            fib = compute_fibonacci_retracement(swing_high, swing_low)
            price = closes[-1]

            rmin = float(self.params.get("retracement_min_pct", 0.20))  # [초기값]
            rmax = float(self.params.get("retracement_max_pct", 0.50))  # [초기값]
            if d == "LONG":
                fib_ok = fib["0.382"] <= price <= fib["0.236"] or (
                    (swing_high - price) / max(swing_high - swing_low, 1e-9)
                    >= rmin
                )
            else:
                fib_ok = True  # SHORT: 대칭 적용 단순화

            atr_ratio_ok = (atr_last / atr_mean20) >= float(self.params.get("atr_ratio_min", 0.8))  # [초기값]
            logger.info(
                "trend_cont symbol=%s dir=%s L1 | "
                "ema_triple=%s(ema20=%.5f ema50=%.5f) "
                "fib_ok=%s(price=%.5f swing_h=%.5f swing_l=%.5f) "
                "atr_ratio_ok=%s(ratio=%.3f min=%.1f)",
                symbol,
                d,
                ema_triple,
                ema20[-1],
                ema50[-1],
                fib_ok,
                price,
                swing_high,
                swing_low,
                atr_ratio_ok,
                atr_last / atr_mean20 if atr_mean20 > 0 else 0,
                float(self.params.get("atr_ratio_min", 0.8)),
            )
            layer1 = ema_triple and fib_ok and atr_ratio_ok
            if not layer1:
                continue

            # ── 레이어 2 ──────────────────────────────────────
            oi_now = float(market_state.get("open_interest", 1))
            oi_prev = float(market_state.get("oi_prev_5m", oi_now))
            oi_ok = oi_now >= oi_prev * 0.98  # OI 유지 또는 증가

            vol_avg20 = float(np.mean(volumes[-21:-1])) if len(volumes) > 20 else volumes[-1]
            vol_decreasing = volumes[-1] < vol_avg20 if vol_avg20 > 0 else True
            logger.info(
                "trend_cont symbol=%s dir=%s L2 | "
                "oi_ok=%s(oi_now=%.1f oi_prev=%.1f) "
                "vol_decreasing=%s(vol=%.1f avg20=%.1f)",
                symbol,
                d,
                oi_ok,
                oi_now,
                oi_prev,
                vol_decreasing,
                volumes[-1],
                vol_avg20,
            )
            layer2 = oi_ok and vol_decreasing
            if not layer2:
                continue

            # ── 레이어 3 ──────────────────────────────────────
            ema20_support = abs(closes[-1] - ema20[-1]) <= atrs[-1] * 0.5
            trig_vol_ratio = float(self.params.get("trigger_volume_ratio_min", 1.2))  # [초기값]
            vol_avg5 = float(np.mean(volumes[-5:])) if len(volumes) >= 5 else volumes[-1]
            trig_vol_ok = volumes[-1] / vol_avg5 >= trig_vol_ratio if vol_avg5 > 0 else False
            logger.info(
                "trend_cont symbol=%s dir=%s L3 | "
                "ema20_support=%s(close=%.5f ema20=%.5f) "
                "trig_vol_ok=%s(ratio=%.3f min=%.1f)",
                symbol,
                d,
                ema20_support,
                closes[-1],
                ema20[-1],
                trig_vol_ok,
                volumes[-1] / vol_avg5 if vol_avg5 > 0 else 0,
                trig_vol_ratio,
            )
            layer3 = ema20_support and trig_vol_ok

            if layer3:
                return True, {"layer1": True, "layer2": True, "layer3": True, "direction": d}

        return False, self._null_hit()

