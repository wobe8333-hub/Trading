from __future__ import annotations

import logging
import math
from typing import Any, Dict, Optional, Tuple

from src.utils.config_loader import ConfigManager

logger = logging.getLogger("growth.position_scaler")

# ── ATR 배수 기본값 (system_config.yaml SSOT) ─────────────────
# Regime → stop/tp ATR 배수 매핑
_STOP_ATR_MAP = {
    "TREND_UP": "stop_atr_trend",  # [초기값] 0.8
    "TREND_DOWN": "stop_atr_trend",  # [초기값] 0.8
    "RANGE": "stop_atr_range",  # [초기값] 0.6
    "EXPANSION": "stop_atr_expansion",  # [초기값] 0.9
}
_TP1_ATR_MAP = {
    "TREND_UP": "tp1_atr_trend",  # [초기값] 1.2
    "TREND_DOWN": "tp1_atr_trend",  # [초기값] 1.2
    "RANGE": "tp1_atr_range",  # [초기값] 1.0
    "EXPANSION": "tp1_atr_expansion",  # [초기값] 1.5
}
_TP2_ATR_MAP = {
    "TREND_UP": "tp2_atr_trend",  # [초기값] 2.0
    "TREND_DOWN": "tp2_atr_trend",  # [초기값] 2.0
    "RANGE": "tp2_atr_range",  # [초기값] 1.4
    "EXPANSION": "tp2_atr_expansion",  # [초기값] 2.2
}
_TP1_RATIO_MAP = {
    "TREND_UP": 0.5,  # [초기값]
    "TREND_DOWN": 0.5,  # [초기값]
    "RANGE": 0.6,  # [초기값]
    "EXPANSION": 0.4,  # [초기값]
}


def _safe(val: Any, default: float = 0.0) -> float:
    try:
        v = float(val)
        return v if math.isfinite(v) else default
    except (TypeError, ValueError):
        return default


class PositionScaler:
    """
    ATR 기반 포지션 사이즈 + 손절/익절 가격 계산.

    모든 ATR 배수는 system_config.yaml SSOT 참조.

    compute_position_size() 공식 (구현지침서 명세):
      stop_multiplier = get_stop_atr_multiplier(regime)
      risk_usd        = equity * risk_pct
      stop_distance   = atr * stop_multiplier
      position_size   = risk_usd / (stop_distance / leverage)
    """

    def __init__(self) -> None:
        self._cfg = ConfigManager().load_system_config()

    def _get_cfg_val(self, key: str, default: float) -> float:
        return _safe(self._cfg.get(key, default), default)

    # ── Stop ATR 배수 ─────────────────────────────────────────

    def get_stop_atr_multiplier(self, regime: str) -> float:
        """
        구현지침서 명세:
        TREND_UP/DOWN → stop_atr_trend
        RANGE         → stop_atr_range
        EXPANSION     → stop_atr_expansion
        """
        cfg_key = _STOP_ATR_MAP.get(regime, "stop_atr_trend")
        return self._get_cfg_val(cfg_key, 0.8)  # [초기값]

    def _get_tp1_multiplier(self, regime: str) -> float:
        cfg_key = _TP1_ATR_MAP.get(regime, "tp1_atr_trend")
        return self._get_cfg_val(cfg_key, 1.2)  # [초기값]

    def _get_tp2_multiplier(self, regime: str) -> float:
        cfg_key = _TP2_ATR_MAP.get(regime, "tp2_atr_trend")
        return self._get_cfg_val(cfg_key, 2.0)  # [초기값]

    # ── 포지션 사이즈 계산 ────────────────────────────────────

    def compute_position_size(
        self,
        equity: float,
        risk_pct: float,
        atr: float,
        regime: str,
        leverage: int = 20,  # [검증값]
    ) -> float:
        """
        구현지침서 명세:
          stop_multiplier = get_stop_atr_multiplier(regime)
          risk_usd        = equity * risk_pct
          stop_distance   = atr * stop_multiplier
          position_size   = risk_usd / (stop_distance / leverage)

        반환: 계약 수 (float)
        """
        try:
            stop_mult = self.get_stop_atr_multiplier(regime)
            risk_usd = equity * risk_pct
            stop_distance = atr * stop_mult

            if stop_distance < 1e-9:
                logger.error("position_scaler stop_distance~0 regime=%s", regime)
                return 0.0

            position_size = risk_usd / (stop_distance / leverage)
            logger.debug(
                "position_scaler regime=%s risk_usd=%.2f stop_dist=%.4f size=%.4f",
                regime,
                risk_usd,
                stop_distance,
                position_size,
            )
            return round(position_size, 4)
        except Exception as exc:
            logger.error(
                "position_scaler compute_position_size failed error=%s", exc
            )
            return 0.0

    # ── Stop Loss 가격 ───────────────────────────────────────

    def compute_stop_price(
        self,
        entry: float,
        atr: float,
        regime: str,
        direction: str,
    ) -> float:
        """
        LONG  → entry - atr * stop_multiplier
        SHORT → entry + atr * stop_multiplier
        """
        try:
            mult = self.get_stop_atr_multiplier(regime)
            if direction == "LONG":
                return round(entry - atr * mult, 8)
            return round(entry + atr * mult, 8)
        except Exception as exc:
            logger.error(
                "position_scaler compute_stop_price failed error=%s", exc
            )
            return entry

    # ── TP1 / TP2 가격 ──────────────────────────────────────

    def compute_tp_prices(
        self,
        entry: float,
        atr: float,
        regime: str,
        direction: str,
    ) -> Tuple[float, float]:
        """
        반환: (tp1_price, tp2_price)
        LONG  → entry + atr * tp1_mult, entry + atr * tp2_mult
        SHORT → entry - atr * tp1_mult, entry - atr * tp2_mult
        """
        try:
            tp1_mult = self._get_tp1_multiplier(regime)
            tp2_mult = self._get_tp2_multiplier(regime)
            if direction == "LONG":
                return (
                    round(entry + atr * tp1_mult, 8),
                    round(entry + atr * tp2_mult, 8),
                )
            return (
                round(entry - atr * tp1_mult, 8),
                round(entry - atr * tp2_mult, 8),
            )
        except Exception as exc:
            logger.error(
                "position_scaler compute_tp_prices failed error=%s", exc
            )
            return entry, entry

    # ── TP1 청산 비율 ────────────────────────────────────────

    def get_tp1_ratio(self, regime: str) -> float:
        """
        구현지침서 명세:
        TREND_UP/DOWN: 0.5, RANGE: 0.6, EXPANSION: 0.4
        """
        return _TP1_RATIO_MAP.get(regime, 0.5)  # [초기값]

