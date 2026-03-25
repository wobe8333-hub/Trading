from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

import numpy as np

from src.strategy.strategy_library.base_strategy import BaseStrategy
from src.utils.math_utils import compute_atr, compute_support_resistance

logger = logging.getLogger("strategy.breakout_momentum")


class BreakoutMomentum(BaseStrategy):
    """
    Breakout Momentum — 3레이어

    레이어 1: Resistance Level 계산 + 돌파 봉 + 거래량
    레이어 2: OI 증가 + imbalance_detector 이벤트
    레이어 3: 되돌림 진입 / Entry Score 90+ 즉시 진입
    """

    def generate_signal(self, symbol, market_state, orderflow_state, direction=None):
        try:
            return self._generate(symbol, market_state, orderflow_state, direction)
        except Exception as exc:
            logger.error(
                "breakout_momentum failed symbol=%s error=%s",
                symbol,
                exc,
            )
            return False, self._null_hit()

    def _generate(self, symbol, market_state, orderflow_state, direction):
        klines = market_state.get("klines_3m") or []
        if len(klines) < 35:
            return False, self._null_hit()

        highs = [float(k.get("high", 0)) for k in klines]
        lows = [float(k.get("low", 0)) for k in klines]
        closes = [float(k.get("close", 0)) for k in klines]
        volumes = [float(k.get("volume", 0)) for k in klines]

        atrs = compute_atr(highs, lows, closes, 14)
        if not atrs:
            return False, self._null_hit()

        _, resistances = compute_support_resistance(
            klines,
            int(self.params.get("resistance_lookback", 30)),  # [초기값]
        )

        if not resistances:
            return False, self._null_hit()

        resistance = resistances[0]
        last_close = closes[-1]
        last_vol = volumes[-1]
        vol_avg20 = float(np.mean(volumes[-21:-1])) if len(volumes) > 20 else last_vol

        # ── 레이어 1: 돌파 봉 + 거래량 ───────────────────────
        breakout = last_close > resistance
        vol_ratio = last_vol / vol_avg20 if vol_avg20 > 0 else 1.0
        vol_spike_ok = vol_ratio >= float(self.params.get("breakout_volume_ratio", 2.0))  # [초기값]
        logger.info(
            "breakout symbol=%s L1 | "
            "breakout=%s(close=%.5f resistance=%.5f) "
            "vol_spike_ok=%s(ratio=%.3f min=%.1f)",
            symbol,
            breakout,
            last_close,
            resistance,
            vol_spike_ok,
            vol_ratio,
            float(self.params.get("breakout_volume_ratio", 2.0)),
        )
        layer1 = breakout and vol_spike_ok
        if not layer1:
            return False, self._null_hit()

        # ── 레이어 2: OI 증가 + imbalance ────────────────────
        oi_now = float(market_state.get("open_interest", 1))
        oi_prev = float(market_state.get("oi_prev_5m", oi_now))
        oi_ok = oi_now > oi_prev

        imb_type = orderflow_state.get("imbalance", {}).get("event_type")
        imb_ok = imb_type in ("IMBALANCE_BREAK", "ABSORPTION_EVENT")
        logger.info(
            "breakout symbol=%s L2 | "
            "oi_ok=%s(oi_now=%.1f oi_prev=%.1f) "
            "imb_ok=%s(imb_type=%s)",
            symbol,
            oi_ok,
            oi_now,
            oi_prev,
            imb_ok,
            imb_type,
        )
        layer2 = oi_ok or imb_ok
        if not layer2:
            return False, self._null_hit()

        # ── 레이어 3: 즉시 진입 (Entry Score 90+ 대리: 조건 완화) ──
        layer3 = True
        logger.info(
            "breakout symbol=%s L3=%s close=%.5f resistance=%.5f vol_ratio=%.3f",
            symbol, layer3, last_close, resistance, vol_ratio,
        )
        return True, {"layer1": True, "layer2": True, "layer3": True, "direction": "LONG"}

