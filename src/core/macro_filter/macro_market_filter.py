from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from src.core.macro_filter.macro_features import MacroFeatureCalculator

logger = logging.getLogger("macro_filter")

# ── 판정 임계값 ───────────────────────────────────────────────
_RISK_OFF_ATR_EXPANSION = 2.5    # [검증값] ATR 급증 기준
_RISK_OFF_OI_DROP = -0.05  # [검증값] OI 5% 이상 급감

_VALID_STATES = frozenset(["BULL", "BEAR", "NEUTRAL", "RISK_OFF"])


class MacroMarketFilter:
    """
    BTC market_state → Macro State 판정 엔진.
    """

    def __init__(self) -> None:
        self._feature_calc = MacroFeatureCalculator()
        self._prev_state: Optional[str] = None

    def get_state(self, btc_market_state: Dict[str, Any]) -> str:
        """
        BTC market_state를 받아 Macro State 문자열 반환.
        반환값: "BULL" / "BEAR" / "NEUTRAL" / "RISK_OFF"
        예외 발생 시 "NEUTRAL" 반환 — 시스템 중단 없음.
        """
        try:
            state = self._evaluate(btc_market_state)
        except Exception as exc:
            logger.error("macro_filter get_state failed error=%s", exc)
            state = "NEUTRAL"

        self._log_state_change(state)
        return state

    def get_features(self, btc_market_state: Dict[str, Any]) -> Dict[str, Any]:
        """feature 딕셔너리만 반환 (디버깅 / 분석용)."""
        return self._feature_calc.compute(btc_market_state)

    # ── 내부 판정 로직 ────────────────────────────────────────

    def _evaluate(self, btc_state: Dict[str, Any]) -> str:
        feat = self._feature_calc.compute(btc_state)

        if (
            feat["atr_expansion"] > _RISK_OFF_ATR_EXPANSION
            and feat["volume_spike"] is True
            and feat["oi_change_pct"] < _RISK_OFF_OI_DROP
        ):
            state = "RISK_OFF"
        elif (
            feat["ema_alignment"] == "BULL"
            and feat["price_vs_vwap"] == "ABOVE"
            and feat["oi_change_pct"] > 0
        ):
            state = "BULL"
        elif (
            feat["ema_alignment"] == "BEAR"
            and feat["price_vs_vwap"] == "BELOW"
            and feat["oi_change_pct"] < 0
        ):
            state = "BEAR"
        else:
            state = "NEUTRAL"

        logger.debug(
            "macro_evaluate result=%s ema_align=%s price_vs_vwap=%s "
            "ema20=%.2f ema50=%.2f atr_exp=%.4f oi_chg=%.6f "
            "funding=%.6f vol_spike=%s",
            state,
            feat.get("ema_alignment"), feat.get("price_vs_vwap"),
            feat.get("ema20", 0.0), feat.get("ema50", 0.0),
            feat.get("atr_expansion", 1.0), feat.get("oi_change_pct", 0.0),
            feat.get("funding_bias", 0.0), feat.get("volume_spike", False),
        )
        return state

    def _log_state_change(self, new_state: str) -> None:
        """이전 상태와 달라진 경우 logs/app/ 에 기록."""
        if new_state != self._prev_state:
            logger.info(
                "macro_filter state_change prev=%s new=%s",
                self._prev_state, new_state,
            )
            self._prev_state = new_state
