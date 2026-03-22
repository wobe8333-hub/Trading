from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

from src.strategy.strategy_library.base_strategy import BaseStrategy
from src.utils.math_utils import compute_atr, compute_support_resistance

logger = logging.getLogger("strategy.stop_hunt_reversal")


class StopHuntReversal(BaseStrategy):
    """
    Stop Hunt Reversal — 3레이어

    레이어 1: 지지선 하방 돌파 + Long Wick + ATR × 0.5 이상
    레이어 2: stop_hunt_detector.detect() confidence >= 기준
    레이어 3: 지지선 위 회복 봉
    """

    def generate_signal(self, symbol, market_state, orderflow_state, direction=None):
        try:
            return self._generate(symbol, market_state, orderflow_state, direction)
        except Exception as exc:
            logger.error(
                "stop_hunt_reversal failed symbol=%s error=%s",
                symbol,
                exc,
            )
            return False, self._null_hit()

    def _generate(self, symbol, market_state, orderflow_state, direction):
        klines = market_state.get("klines_3m") or []
        if len(klines) < 15:
            return False, self._null_hit()

        highs = [float(k.get("high", 0)) for k in klines]
        lows = [float(k.get("low", 0)) for k in klines]
        closes = [float(k.get("close", 0)) for k in klines]
        opens = [float(k.get("open", 0)) for k in klines]

        atrs = compute_atr(highs, lows, closes, 14)
        if not atrs:
            return False, self._null_hit()

        atr = atrs[-1]
        supports, _ = compute_support_resistance(
            klines,
            int(self.params.get("support_lookback", 10)),  # [초기값]
        )

        if not supports:
            return False, self._null_hit()

        support = supports[0]
        last_low = lows[-1]
        last_high = highs[-1]
        last_close = closes[-1]
        last_open = opens[-1]

        body = abs(last_close - last_open)
        lower_wick = min(last_open, last_close) - last_low
        lower_wick = max(lower_wick, 0.0)

        # ── 레이어 1 ──────────────────────────────────────────
        swept = last_low < support
        wick_body_ok = (
            lower_wick
            >= body * float(self.params.get("wick_body_ratio_min", 2.0))  # [초기값]
            if body > 1e-9 else False
        )
        wick_atr_ok = lower_wick >= atr * float(self.params.get("wick_atr_multiplier_min", 0.5))  # [검증값]
        logger.info(
            "stop_hunt symbol=%s L1 | "
            "swept=%s(low=%.6f support=%.6f) "
            "wick_body_ok=%s(wick=%.6f body=%.6f ratio=%.2f min=%.1f) "
            "wick_atr_ok=%s(wick=%.6f atr_mult=%.6f)",
            symbol,
            swept,
            last_low,
            support,
            wick_body_ok,
            lower_wick,
            body,
            lower_wick / body if body > 1e-9 else 0,
            float(self.params.get("wick_body_ratio_min", 2.0)),
            wick_atr_ok,
            lower_wick,
            atr * float(self.params.get("wick_atr_multiplier_min", 0.5)),
        )
        layer1 = swept and wick_body_ok and wick_atr_ok
        if not layer1:
            return False, self._null_hit()

        # ── 레이어 2: stop_hunt confidence ────────────────────
        sh_conf = float(orderflow_state.get("stop_hunt", {}).get("confidence", 0.0))
        min_conf = float(self.params.get("stop_hunt_confidence_min", 0.65))  # [초기값]
        logger.info(
            "stop_hunt symbol=%s L2 | sh_conf=%.3f min_conf=%.2f ok=%s",
            symbol,
            sh_conf,
            min_conf,
            sh_conf >= min_conf,
        )
        layer2 = sh_conf >= min_conf
        if not layer2:
            return False, {"layer1": True, "layer2": False, "layer3": False, "direction": None}

        # ── 레이어 3: 지지선 위 회복 클로즈 ──────────────────
        layer3 = last_close > support
        if layer3:
            return True, {"layer1": True, "layer2": True, "layer3": True, "direction": "LONG"}

        return False, {"layer1": True, "layer2": True, "layer3": False, "direction": None}

