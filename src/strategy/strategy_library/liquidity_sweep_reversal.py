from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

from src.strategy.strategy_library.base_strategy import BaseStrategy
from src.utils.math_utils import compute_atr, compute_support_resistance

logger = logging.getLogger("strategy.liquidity_sweep_reversal")


class LiquiditySweepReversal(BaseStrategy):
    """
    Liquidity Sweep Reversal — 3레이어

    레이어 1: Support Level 계산 + 스윕 봉 감지 + 회복 확인
    레이어 2: stop_hunt_detector confidence >= stop_hunt_confidence_min
    레이어 3: Support 위 회복 클로즈
    """

    def generate_signal(self, symbol, market_state, orderflow_state, direction=None):
        try:
            return self._generate(symbol, market_state, orderflow_state, direction)
        except Exception as exc:
            logger.error(
                "liquidity_sweep_reversal failed symbol=%s error=%s",
                symbol,
                exc,
            )
            return False, self._null_hit()

    def _generate(self, symbol, market_state, orderflow_state, direction):
        klines = market_state.get("klines_3m") or []
        if len(klines) < 25:
            return False, self._null_hit()

        highs = [float(k.get("high", 0)) for k in klines]
        lows = [float(k.get("low", 0)) for k in klines]
        closes = [float(k.get("close", 0)) for k in klines]

        atrs = compute_atr(highs, lows, closes, 14)
        if not atrs:
            return False, self._null_hit()

        supports, resistances = compute_support_resistance(
            klines,
            int(self.params.get("support_lookback", 20)),  # [초기값]
        )

        last = klines[-1]
        last_low = float(last.get("low", 0))
        last_high = float(last.get("high", 0))
        last_close = float(last.get("close", 0))

        logger.info(
            "liq_sweep symbol=%s | supports=%d resistance=%d last_low=%.5f last_close=%.5f",
            symbol,
            len(supports),
            len(resistances),
            last_low,
            last_close,
        )

        # ── BULL_HUNT (롱 기회) ────────────────────────────────
        if direction in (None, "LONG") and supports:
            support_level = supports[0]
            swept = last_low < support_level

            if swept:
                recovery = last_close > support_level
                layer1 = swept and recovery
                logger.info(
                    "liq_sweep symbol=%s L1 | "
                    "swept=%s(low=%.5f support=%.5f) recovery=%s(close=%.5f) layer1=%s",
                    symbol,
                    swept,
                    last_low,
                    support_level,
                    recovery,
                    last_close,
                    layer1,
                )

                if layer1:
                    sh_conf = float(
                        orderflow_state.get("stop_hunt", {}).get(
                            "confidence", 0.0
                        )
                    )
                    min_conf = float(
                        self.params.get(
                            "stop_hunt_confidence_min",
                            0.65,
                        )
                    )  # [초기값]
                    layer2 = sh_conf >= min_conf
                    logger.info(
                        "liq_sweep symbol=%s L2 | sh_conf=%.3f min_conf=%.2f ok=%s",
                        symbol,
                        sh_conf,
                        min_conf,
                        layer2,
                    )

                    if layer2:
                        layer3 = last_close > support_level
                        logger.info(
                            "liq_sweep symbol=%s L3 | close=%.5f support=%.5f ok=%s",
                            symbol,
                            last_close,
                            support_level,
                            layer3,
                        )
                        if layer3:
                            return True, {
                                "layer1": True,
                                "layer2": True,
                                "layer3": True,
                                "direction": "LONG",
                            }

        return False, self._null_hit()

