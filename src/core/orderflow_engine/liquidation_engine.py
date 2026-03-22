from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger("orderflow.liquidation")

# ── 감지 임계값 ───────────────────────────────────────────────
_OI_DROP_1M_THRESHOLD     = -0.03    # [초기값] OI 1분 3% 감소
_PRICE_IMPULSE_THRESHOLD  = -2.0     # [초기값] 하방 2ATR 급락
_VOLUME_SPIKE_THRESHOLD   = 3.0      # [초기값] 거래량 3배
_MIN_OI_DROP_USD          = 500_000  # [초기값] 최소 청산 규모

# confidence 가산 기준
_CONF_OI_DROP_DEEP   = -0.05    # [초기값]
_CONF_SPIKE_DEEP     = 5.0      # [초기값]
_CONF_OI_DROP_LARGE  = 1_000_000 # [초기값]


class LiquidationEngine:
    """
    강제청산 캐스케이드 감지 엔진.
    """

    def detect(
        self, symbol: str, features: Dict[str, Any]
    ) -> Dict[str, Any]:
        try:
            return self._detect(symbol, features)
        except Exception as exc:
            logger.error(
                "liquidation_engine detect failed symbol=%s error=%s",
                symbol, exc,
            )
            return self._null_result()

    def _detect(
        self, symbol: str, features: Dict[str, Any]
    ) -> Dict[str, Any]:
        oi_change_1m    = float(features.get("oi_change_1m_pct",   0.0))
        price_impulse   = float(features.get("price_impulse_atr",   0.0))
        vol_spike       = float(features.get("volume_spike_ratio",  1.0))
        absorption      = bool(features.get("absorption_signal",    False))
        open_interest   = float(features.get("open_interest",       0.0))

        oi_drop_usd = abs(oi_change_1m) * open_interest

        # ── SHORT_LIQUIDATION_CASCADE (숏 청산 → 롱 기회) ────
        short_liq = (
            oi_change_1m  < _OI_DROP_1M_THRESHOLD
            and price_impulse < _PRICE_IMPULSE_THRESHOLD
            and vol_spike     > _VOLUME_SPIKE_THRESHOLD
            and oi_drop_usd   >= _MIN_OI_DROP_USD
        )

        # ── LONG_LIQUIDATION_CASCADE (롱 청산 → 숏 기회) ─────
        long_liq = (
            oi_change_1m  < _OI_DROP_1M_THRESHOLD
            and price_impulse > abs(_PRICE_IMPULSE_THRESHOLD)
            and vol_spike     > _VOLUME_SPIKE_THRESHOLD
            and oi_drop_usd   >= _MIN_OI_DROP_USD
        )

        if not (short_liq or long_liq):
            return self._null_result()

        event_type = (
            "SHORT_LIQUIDATION_CASCADE" if short_liq
            else "LONG_LIQUIDATION_CASCADE"
        )

        confidence = self._compute_confidence(
            oi_change_1m, vol_spike, absorption, oi_drop_usd
        )

        logger.info(
            "liquidation_engine event=%s symbol=%s confidence=%.2f",
            event_type, symbol, confidence,
        )

        return {
            "event_type":      event_type,
            "confidence":      round(confidence, 4),
            "oi_drop_pct":     round(oi_change_1m, 6),
            "min_oi_drop_usd": round(oi_drop_usd, 2),
        }

    @staticmethod
    def _compute_confidence(
        oi_change_1m: float,
        vol_spike: float,
        absorption: bool,
        oi_drop_usd: float,
    ) -> float:
        """
        구현지침서 명세:
          base = 0.5
          if oi_change_1m_pct < -0.05: base += 0.15
          if volume_spike_ratio > 5.0: base += 0.15
          if absorption_signal:        base += 0.10
          if oi_drop_usd > 1_000_000: base += 0.10
          return min(base, 1.0)
        """
        base = 0.5
        if oi_change_1m < _CONF_OI_DROP_DEEP:    # [초기값] -0.05
            base += 0.15
        if vol_spike > _CONF_SPIKE_DEEP:          # [초기값] 5.0
            base += 0.15
        if absorption:
            base += 0.10
        if oi_drop_usd > _CONF_OI_DROP_LARGE:    # [초기값] 1_000_000
            base += 0.10
        return min(base, 1.0)

    @staticmethod
    def _null_result() -> Dict[str, Any]:
        return {
            "event_type":      None,
            "confidence":      0.0,
            "oi_drop_pct":     0.0,
            "min_oi_drop_usd": 0.0,
        }
