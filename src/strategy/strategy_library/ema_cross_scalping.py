from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

import numpy as np

from src.strategy.strategy_library.base_strategy import BaseStrategy
from src.utils.math_utils import compute_ema

logger = logging.getLogger("strategy.ema_cross_scalping")


class EMACrossScalping(BaseStrategy):
    """
    EMA 위치 관계 + Rolling VWAP 스캘핑 — 3레이어

    레이어 1:
      LONG:  EMA5>EMA20 이고 종가 > rolling VWAP(최근 vwap_lookback 봉)
      SHORT: EMA5<EMA20 이고 종가 < rolling VWAP

    레이어 2: 거래량 >= 직전 20봉 평균 × volume_ratio_min
    레이어 3: LONG 양봉 / SHORT 음봉
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

        if not (ema_fast and ema_slow):
            return False, self._null_hit()

        # ── Rolling VWAP (내부 전용 — compute_vwap 전역 함수 미사용) ──
        vwap_lookback = int(self.params.get("vwap_lookback", 20))  # [초기값]
        rc = closes[-vwap_lookback:]
        rv = volumes[-vwap_lookback:]
        pv_sum = sum(c * v for c, v in zip(rc, rv))
        vol_sum = sum(rv)
        rolling_vwap = pv_sum / vol_sum if vol_sum > 0 else closes[-1]

        ef_now = ema_fast[-1]
        es_now = ema_slow[-1]
        price = closes[-1]

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
            # ── 레이어 1: EMA 위치 관계 + Rolling VWAP 방향 ──
            # 교차 순간이 아닌 "현재 위치 관계"로 판단
            if d == "LONG":
                ema_ok = ef_now > es_now  # EMA5 > EMA20 (상승 모멘텀)
                vwap_ok = price > rolling_vwap  # 가격 VWAP 위
            else:
                ema_ok = ef_now < es_now  # EMA5 < EMA20 (하락 모멘텀)
                vwap_ok = price < rolling_vwap  # 가격 VWAP 아래

            layer1 = ema_ok and vwap_ok
            logger.info(
                "ema_cross symbol=%s dir=%s L1=%s | "
                "ema_ok=%s(ef=%.5f es=%.5f) "
                "vwap_ok=%s(price=%.5f rvwap=%.5f)",
                symbol,
                d,
                layer1,
                ema_ok,
                ef_now,
                es_now,
                vwap_ok,
                price,
                rolling_vwap,
            )
            if not layer1:
                continue

            # ── 레이어 2: 거래량 확인 ────────────────────────
            vol_ratio = volumes[-1] / vol_avg20
            layer2 = vol_ratio >= vol_ratio_min
            logger.info(
                "ema_cross symbol=%s dir=%s L2=%s | "
                "vol_ratio=%.3f min=%.1f",
                symbol,
                d,
                layer2,
                vol_ratio,
                vol_ratio_min,
            )
            if not layer2:
                continue

            # ── 레이어 3: 방향 확인 봉 ───────────────────────
            if d == "LONG":
                layer3 = closes[-1] > opens[-1]  # 양봉
            else:
                layer3 = closes[-1] < opens[-1]  # 음봉

            logger.info(
                "ema_cross symbol=%s dir=%s L3=%s | "
                "close=%.5f open=%.5f",
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

        logger.info("ema_cross symbol=%s NO_SIGNAL", symbol)
        return False, self._null_hit()
