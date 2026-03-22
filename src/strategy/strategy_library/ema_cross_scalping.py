from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

import numpy as np

from src.strategy.strategy_library.base_strategy import BaseStrategy
from src.utils.math_utils import compute_ema, compute_vwap

logger = logging.getLogger("strategy.ema_cross_scalping")


class EMACrossScalping(BaseStrategy):
    """
    EMA Cross OR VWAP Cross Scalping — 3레이어

    레이어 1 (진입 구조 감지):
      다음 중 하나 이상 충족:
        A. EMA 교차: 직전봉 EMA5<=EMA20, 현재봉 EMA5>EMA20 (LONG 골든크로스)
                    직전봉 EMA5>=EMA20, 현재봉 EMA5<EMA20 (SHORT 데드크로스)
        B. VWAP 교차: 직전봉 가격<=VWAP, 현재봉 가격>VWAP (LONG)
                      직전봉 가격>=VWAP, 현재봉 가격<VWAP (SHORT)

    레이어 2 (거래량 확인):
      현재 거래량 >= 직전 20봉 평균 × volume_ratio_min

    레이어 3 (방향 확인 봉):
      LONG:  현재봉 양봉 (close > open)
      SHORT: 현재봉 음봉 (close < open)
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
                "ema_cross_scalping generate_signal failed symbol=%s error=%s",
                symbol,
                exc,
            )
            return False, self._null_hit()

    def _generate(self, symbol, market_state, orderflow_state, direction):
        klines = market_state.get("klines_3m") or []
        if len(klines) < 25:
            return False, self._null_hit()

        closes = [float(k.get("close", 0)) for k in klines]
        opens = [float(k.get("open", 0)) for k in klines]
        volumes = [float(k.get("volume", 0)) for k in klines]

        ema_fast_p = int(self.params.get("ema_fast", 5))  # [초기값]
        ema_slow_p = int(self.params.get("ema_slow", 20))  # [초기값]

        ema_fast = compute_ema(closes, ema_fast_p)
        ema_slow = compute_ema(closes, ema_slow_p)
        vwaps = compute_vwap(closes, volumes)

        if not (ema_fast and ema_slow and vwaps):
            return False, self._null_hit()
        if len(ema_fast) < 2 or len(ema_slow) < 2 or len(vwaps) < 2:
            return False, self._null_hit()

        ef_now = ema_fast[-1]
        ef_prev = ema_fast[-2]
        es_now = ema_slow[-1]
        es_prev = ema_slow[-2]
        vwap_now = vwaps[-1]
        vwap_prev = vwaps[-2]

        vol_avg20 = (
            float(np.mean(volumes[-21:-1]))
            if len(volumes) > 20
            else (volumes[-1] if volumes else 1.0)
        )
        vol_avg20 = vol_avg20 if vol_avg20 > 0 else 1.0
        vol_ratio_min = float(self.params.get("volume_ratio_min", 1.0))  # [초기값]

        directions = []
        if direction in (None, "LONG"):
            directions.append("LONG")
        if direction in (None, "SHORT"):
            directions.append("SHORT")

        for d in directions:
            if d == "LONG":
                ema_cross = ef_prev <= es_prev and ef_now > es_now
                vwap_cross = closes[-2] <= vwap_prev and closes[-1] > vwap_now
            else:
                ema_cross = ef_prev >= es_prev and ef_now < es_now
                vwap_cross = closes[-2] >= vwap_prev and closes[-1] < vwap_now

            layer1 = ema_cross or vwap_cross
            logger.info(
                "ema_cross symbol=%s dir=%s L1=%s | "
                "ema_cross=%s(ef_prev=%.5f es_prev=%.5f ef_now=%.5f es_now=%.5f) "
                "vwap_cross=%s(c[-2]=%.5f vwap_prev=%.5f c[-1]=%.5f vwap_now=%.5f)",
                symbol,
                d,
                layer1,
                ema_cross,
                ef_prev,
                es_prev,
                ef_now,
                es_now,
                vwap_cross,
                closes[-2],
                vwap_prev,
                closes[-1],
                vwap_now,
            )
            if not layer1:
                continue

            vol_ratio = volumes[-1] / vol_avg20
            layer2 = vol_ratio >= vol_ratio_min
            logger.info(
                "ema_cross symbol=%s dir=%s L2=%s | "
                "vol_ratio=%.3f min=%.1f vol_now=%.1f vol_avg20=%.1f",
                symbol,
                d,
                layer2,
                vol_ratio,
                vol_ratio_min,
                volumes[-1],
                vol_avg20,
            )
            if not layer2:
                continue

            if d == "LONG":
                layer3 = closes[-1] > opens[-1]
            else:
                layer3 = closes[-1] < opens[-1]

            logger.info(
                "ema_cross symbol=%s dir=%s L3=%s | close=%.5f open=%.5f",
                symbol,
                d,
                layer3,
                closes[-1],
                opens[-1],
            )
            if layer3:
                return True, {
                    "layer1": True,
                    "layer2": True,
                    "layer3": True,
                    "direction": d,
                }

        logger.info("ema_cross symbol=%s NO_SIGNAL — 모든 방향 차단", symbol)
        return False, self._null_hit()
