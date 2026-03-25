from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

from src.strategy.strategy_library.base_strategy import BaseStrategy
from src.utils.math_utils import compute_atr

logger = logging.getLogger("strategy.liquidation_scalping")


class LiquidationScalping(BaseStrategy):
    """
    Liquidation Scalping — 3레이어

    레이어 1: OI 급감 + 가격 급락 + 최소 청산 규모
    레이어 2: liquidation_engine.detect() confidence >= 기준
    레이어 3: 반등 봉 고점 50% 회복
    """

    def generate_signal(self, symbol, market_state, orderflow_state, direction=None):
        try:
            return self._generate(symbol, market_state, orderflow_state, direction)
        except Exception as exc:
            logger.error(
                "liquidation_scalping failed symbol=%s error=%s",
                symbol,
                exc,
            )
            return False, self._null_hit()

    def _generate(self, symbol, market_state, orderflow_state, direction):
        klines = market_state.get("klines_3m") or []
        if len(klines) < 16:
            return False, self._null_hit()

        highs = [float(k.get("high", 0)) for k in klines]
        lows = [float(k.get("low", 0)) for k in klines]
        closes = [float(k.get("close", 0)) for k in klines]

        atrs = compute_atr(highs, lows, closes, 14)
        atr = atrs[-1] if atrs else 0.0
        if atr < 1e-9:
            return False, self._null_hit()

        oi_now = float(market_state.get("open_interest", 1))
        oi_prev = float(market_state.get("oi_prev_5m", oi_now))
        oi_drop = (oi_now - oi_prev) / oi_prev if oi_prev > 1e-9 else 0.0
        oi_drop_usd = abs(oi_drop) * oi_now

        price_drop = (closes[-1] - closes[-2]) / atr if len(closes) >= 2 else 0.0

        # ── 레이어 1 ──────────────────────────────────────────
        oi_drop_ok = oi_drop < -float(self.params.get("oi_drop_pct_1min", 0.03))  # [초기값]
        price_ok = price_drop < -float(self.params.get("price_drop_atr_multiplier", 2.0))  # [초기값]
        min_usd_ok = oi_drop_usd > float(self.params.get("min_oi_drop_usd", 500_000))  # [초기값]
        logger.info(
            "liq_scalp symbol=%s L1 | "
            "oi_drop_ok=%s(drop=%.4f min=%.2f) "
            "price_ok=%s(drop_atr=%.3f min=%.1f) "
            "min_usd_ok=%s(usd=%.0f min=%.0f)",
            symbol,
            oi_drop_ok,
            oi_drop,
            float(self.params.get("oi_drop_pct_1min", 0.03)),
            price_ok,
            price_drop,
            float(self.params.get("price_drop_atr_multiplier", 2.0)),
            min_usd_ok,
            oi_drop_usd,
            float(self.params.get("min_oi_drop_usd", 500_000)),
        )
        layer1 = oi_drop_ok and price_ok and min_usd_ok
        if not layer1:
            return False, self._null_hit()

        # ── 레이어 2: liquidation confidence ──────────────────
        liq_conf = float(
            orderflow_state.get("liquidation", {}).get("confidence", 0.0)
        )
        min_conf = float(self.params.get("liquidation_confidence_min", 0.75))  # [초기값]
        layer2 = liq_conf >= min_conf
        logger.info(
            "liq_scalp symbol=%s L2=%s liq_conf=%.3f min_conf=%.3f",
            symbol, layer2, liq_conf, min_conf,
        )
        if not layer2:
            return False, {"layer1": True, "layer2": False, "layer3": False, "direction": None}

        # ── 레이어 3: 반등 봉 고점 50% 회복 ──────────────────
        if len(klines) >= 2:
            prev_range = highs[-2] - lows[-2]
            recovery_pct = float(self.params.get("recovery_pct_min", 0.50))
            recovery_ok = (closes[-1] - lows[-1]) >= prev_range * recovery_pct
        else:
            recovery_ok = False

        layer3 = recovery_ok
        logger.info(
            "liq_scalp symbol=%s L3=%s "
            "close=%.5f low=%.5f prev_range=%.5f recovery_pct=%.2f",
            symbol, layer3,
            closes[-1] if closes else 0.0,
            lows[-1] if lows else 0.0,
            prev_range if len(klines) >= 2 else 0.0,
            float(self.params.get("recovery_pct_min", 0.50)),
        )
        if layer3:
            return True, {"layer1": True, "layer2": True, "layer3": True, "direction": "LONG"}

        return False, {"layer1": True, "layer2": True, "layer3": False, "direction": None}

