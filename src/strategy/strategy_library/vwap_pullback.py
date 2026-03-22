from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

import numpy as np

from src.strategy.strategy_library.base_strategy import BaseStrategy
from src.utils.math_utils import (
    compute_ema,
    compute_atr,
    compute_vwap,
    count_pullback_candles,
)

logger = logging.getLogger("strategy.vwap_pullback")


class VWAPPullback(BaseStrategy):
    """
    VWAP Pullback 전략 — 3레이어 진입 조건

    레이어 1 (구조 확인)
      - EMA20 > EMA50 (LONG) / EMA20 < EMA50 (SHORT)
      - 현재가 VWAP ± band 이내
      - 풀백 이전 VWAP 반대편에 있었음
      - pullback_candles_min <= 풀백 봉 수 <= pullback_candles_max
      - 풀백 ATR 비율 <= pullback_atr_ratio_max

    레이어 2 (Orderbook 확인)
      - bid_ask_ratio >= bid_ask_ratio_min
      - 풀백 중 거래량 <= 평균 * pullback_volume_ratio_max

    레이어 3 (트리거 확인)
      - VWAP 재돌파 (전봉 < VWAP, 현봉 > VWAP)
      - 트리거 봉 거래량 >= 직전 5봉 평균 * trigger_volume_ratio_min
    """

    def generate_signal(
        self,
        symbol: str,
        market_state: Dict[str, Any],
        orderflow_state: Dict[str, Any],
        direction: Optional[str] = None,
    ) -> Tuple[bool, Dict[str, Any]]:
        try:
            return self._generate(symbol, market_state, orderflow_state, direction)
        except Exception as exc:
            logger.error(
                "vwap_pullback generate_signal failed symbol=%s error=%s",
                symbol,
                exc,
            )
            return False, self._null_hit()

    def _generate(
        self,
        symbol,
        market_state,
        orderflow_state,
        direction,
    ):
        klines = market_state.get("klines_3m") or []
        if len(klines) < 55:
            return False, self._null_hit()

        closes = [float(k.get("close", 0)) for k in klines]
        highs = [float(k.get("high", 0)) for k in klines]
        lows = [float(k.get("low", 0)) for k in klines]
        volumes = [float(k.get("volume", 0)) for k in klines]

        ema20 = compute_ema(closes, 5)  # [초기값] EMA5  — 3분봉×5=15분 단기
        ema50 = compute_ema(closes, 20)  # [초기값] EMA20 — 3분봉×20=60분 중단기
        vwap = compute_vwap(closes, volumes)
        atrs = compute_atr(highs, lows, closes, 14)

        if not (ema20 and ema50 and vwap and atrs):
            return False, self._null_hit()

        atr_last = atrs[-1]
        atr_mean20 = float(np.mean(atrs[-20:])) if len(atrs) >= 20 else atr_last
        if atr_mean20 < 1e-9:
            return False, self._null_hit()

        band = vwap[-1] * float(self.params.get("vwap_band_pct", 0.0015))  # [초기값]
        bid_ask = float(market_state.get("bid_ask_ratio", 1.0))

        directions = []
        if direction in (None, "LONG"):
            directions.append("LONG")
        if direction in (None, "SHORT"):
            directions.append("SHORT")

        for d in directions:
            hit = self._check_direction(
                symbol,
                d,
                closes,
                ema20,
                ema50,
                vwap,
                volumes,
                atrs,
                atr_last,
                atr_mean20,
                band,
                bid_ask,
            )
            if hit["layer3"]:
                return True, hit

        return False, self._null_hit()

    def _check_direction(
        self,
        symbol,
        d,
        closes,
        ema20,
        ema50,
        vwap,
        volumes,
        atrs,
        atr_last,
        atr_mean20,
        band,
        bid_ask,
    ):
        null = self._null_hit()

        # ── 레이어 1 ──────────────────────────────────────────
        ema_ok = ema20[-1] > ema50[-1] if d == "LONG" else ema20[-1] < ema50[-1]
        near_vwap = abs(closes[-1] - vwap[-1]) <= band

        pb_len = count_pullback_candles(closes, vwap, d)
        pb_min = int(self.params.get("pullback_candles_min", 2))  # [초기값]
        pb_max = int(self.params.get("pullback_candles_max", 5))  # [초기값]
        pb_ok = pb_min <= pb_len <= pb_max

        pb_atr_ratio = atr_last / atr_mean20
        pb_atr_ok = pb_atr_ratio <= float(self.params.get("pullback_atr_ratio_max", 0.7))  # [초기값]

        logger.info(
            "vwap_pb symbol=%s dir=%s L1 | "
            "ema_ok=%s(ema20=%.5f ema50=%.5f) "
            "near_vwap=%s(diff=%.6f band=%.6f) "
            "pb_ok=%s(pb_len=%d min=%d max=%d) "
            "pb_atr_ok=%s(ratio=%.3f max=%.2f)",
            symbol,
            d,
            ema_ok,
            ema20[-1],
            ema50[-1],
            near_vwap,
            abs(closes[-1] - vwap[-1]),
            band,
            pb_ok,
            pb_len,
            pb_min,
            pb_max,
            pb_atr_ok,
            pb_atr_ratio,
            float(self.params.get("pullback_atr_ratio_max", 0.7)),
        )
        layer1 = ema_ok and near_vwap and pb_ok and pb_atr_ok
        if not layer1:
            return {**null, "layer1": False}

        # ── 레이어 2 ──────────────────────────────────────────
        ba_min = float(self.params.get("bid_ask_ratio_min", 1.2))  # [초기값]
        ba_ok = bid_ask >= ba_min if d == "LONG" else bid_ask <= (1.0 / ba_min)

        vol_avg20 = float(np.mean(volumes[-20:])) if len(volumes) >= 20 else volumes[-1]
        pb_vol_ratio = volumes[-1] / vol_avg20 if vol_avg20 > 0 else 1.0
        pb_vol_ok = pb_vol_ratio <= float(self.params.get("pullback_volume_ratio_max", 0.7))  # [초기값]

        logger.info(
            "vwap_pb dir=%s L2 | "
            "ba_ok=%s(bid_ask=%.3f min=%.2f) "
            "pb_vol_ok=%s(ratio=%.3f max=%.2f)",
            d,
            ba_ok,
            bid_ask,
            ba_min,
            pb_vol_ok,
            pb_vol_ratio,
            float(self.params.get("pullback_volume_ratio_max", 0.7)),
        )
        layer2 = ba_ok and pb_vol_ok
        if not layer2:
            return {**null, "layer1": True, "layer2": False}

        # ── 레이어 3 ──────────────────────────────────────────
        if d == "LONG":
            cross_vwap = len(closes) >= 2 and closes[-2] <= vwap[-2] and closes[-1] > vwap[-1]
        else:
            cross_vwap = len(closes) >= 2 and closes[-2] >= vwap[-2] and closes[-1] < vwap[-1]

        vol_avg5 = float(np.mean(volumes[-5:])) if len(volumes) >= 5 else volumes[-1]
        trig_vol = volumes[-1] / vol_avg5 if vol_avg5 > 0 else 1.0
        trig_ok = trig_vol >= float(self.params.get("trigger_volume_ratio_min", 1.2))  # [초기값]

        logger.info(
            "vwap_pb dir=%s L3 | "
            "cross_vwap=%s(c[-2]=%.5f vwap[-2]=%.5f c[-1]=%.5f vwap[-1]=%.5f) "
            "trig_vol_ok=%s(ratio=%.3f min=%.2f)",
            d,
            cross_vwap,
            closes[-2],
            vwap[-2],
            closes[-1],
            vwap[-1],
            trig_ok,
            trig_vol,
            float(self.params.get("trigger_volume_ratio_min", 1.2)),
        )
        layer3 = cross_vwap and trig_ok
        return {
            "layer1": True,
            "layer2": True,
            "layer3": layer3,
            "direction": d if layer3 else None,
        }

