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
        return self._get_cfg_val(cfg_key, 1.2)  # [수정6] SL 거리 확대 — 단기 노이즈 청산 방지

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
        leverage: int = 20,         # [검증값]
        entry_price: float = 0.0,   # [FIX 16] max_capital_usage 캡 계산용
    ) -> float:
        """
        FIX 11: position_size = risk_usd / stop_distance  (leverage 제거)
        FIX 16: min(risk_based_size, max_capital_usage 캡) 적용

        stop_multiplier = get_stop_atr_multiplier(regime)
        risk_usd        = equity * risk_pct
        stop_distance   = atr * stop_multiplier
        risk_based_size = risk_usd / stop_distance
        max_size        = (equity * max_capital_usage * leverage) / entry_price
        position_size   = min(risk_based_size, max_size)
        """
        try:
            stop_mult     = self.get_stop_atr_multiplier(regime)
            risk_usd      = equity * risk_pct
            stop_distance = atr * stop_mult

            if stop_distance < 1e-9:
                logger.error(
                    "position_scaler stop_distance~0 regime=%s atr=%s",
                    regime, atr,
                )
                return 0.0

            # FIX 11: leverage 제거
            risk_based_size = risk_usd / stop_distance

            # FIX 16: max_capital_usage 캡 적용
            if entry_price > 1e-9:
                max_capital_usage = float(
                    self._cfg.get("max_capital_usage", 0.25)  # [검증값]
                )
                max_size_by_capital = (
                    equity * max_capital_usage * leverage
                ) / entry_price
                position_size = min(risk_based_size, max_size_by_capital)
            else:
                position_size = risk_based_size

            logger.info(
                "position_scaler SIZE regime=%s "
                "equity=%.2f risk_pct=%.5f risk_usd=%.2f "
                "atr=%.5f stop_mult=%.3f stop_dist=%.6f "
                "risk_based=%.4f final=%.4f entry=%.5f",
                regime,
                equity, risk_pct, risk_usd,
                atr, stop_mult, stop_distance,
                risk_based_size, position_size, entry_price,
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
                _stop = round(entry - atr * mult, 8)
            else:
                _stop = round(entry + atr * mult, 8)
            logger.info(
                "position_scaler STOP regime=%s dir=%s "
                "entry=%.5f atr=%.5f mult=%.3f stop=%.5f",
                regime, direction, entry, atr, mult, _stop,
            )
            return _stop
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
                _tp1 = round(entry + atr * tp1_mult, 8)
                _tp2 = round(entry + atr * tp2_mult, 8)
            else:
                _tp1 = round(entry - atr * tp1_mult, 8)
                _tp2 = round(entry - atr * tp2_mult, 8)
            logger.info(
                "position_scaler TP regime=%s dir=%s "
                "entry=%.5f atr=%.5f tp1_mult=%.3f tp2_mult=%.3f "
                "tp1=%.5f tp2=%.5f",
                regime, direction, entry, atr, tp1_mult, tp2_mult, _tp1, _tp2,
            )
            return _tp1, _tp2
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

