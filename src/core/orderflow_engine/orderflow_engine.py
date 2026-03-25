from __future__ import annotations

import logging
from typing import Any, Dict

from src.core.orderflow_engine.imbalance_detector import ImbalanceDetector
from src.core.orderflow_engine.liquidation_engine import LiquidationEngine
from src.core.orderflow_engine.orderflow_features import OrderflowFeatureCalculator
from src.core.orderflow_engine.stop_hunt_detector import StopHuntDetector

logger = logging.getLogger("orderflow")


class OrderflowEngine:
    """
    Orderflow 통합 오케스트레이터.
    """

    def __init__(self) -> None:
        self._feature_calc = OrderflowFeatureCalculator()
        self._liq_engine   = LiquidationEngine()
        self._stop_hunt    = StopHuntDetector()
        self._imbalance    = ImbalanceDetector()

    def compute(
        self, symbol: str, market_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        market_state → orderflow_state 딕셔너리 반환.
        예외 발생 시 모든 confidence=0.0인 null 상태 반환 — 시스템 중단 없음.
        """
        try:
            return self._compute(symbol, market_state)
        except Exception as exc:
            logger.error(
                "orderflow_engine compute failed symbol=%s error=%s",
                symbol, exc,
            )
            return self._null_state()

    def _compute(
        self, symbol: str, market_state: Dict[str, Any]
    ) -> Dict[str, Any]:
        # 1. Feature 계산
        features = self._feature_calc.compute(symbol, market_state)

        # open_interest를 features에 주입 (LiquidationEngine에서 사용)
        features["open_interest"] = float(
            market_state.get("open_interest") or 0.0
        )

        # 2. 각 감지기 실행
        liq_result       = self._liq_engine.detect(symbol, features)
        stop_hunt_result = self._stop_hunt.detect(symbol, market_state, features)
        imbalance_result = self._imbalance.detect(symbol, market_state)

        # 3. max_confidence
        max_conf = max(
            float(liq_result.get("confidence",       0.0)),
            float(stop_hunt_result.get("confidence", 0.0)),
            float(imbalance_result.get("confidence", 0.0)),
        )

        state = {
            "liquidation":    liq_result,
            "stop_hunt":      stop_hunt_result,
            "imbalance":      imbalance_result,
            "max_confidence": round(max_conf, 4),
        }

        logger.info(
            "orderflow_engine symbol=%s max_conf=%.2f "
            "liq=%s liq_conf=%.3f hunt=%s hunt_conf=%.3f imb=%s imb_conf=%.3f | "
            "oi_chg_1m=%.5f vol_spike=%.3f price_impulse=%.4f "
            "trade_vel=%.0f absorption=%s",
            symbol, max_conf,
            liq_result.get("event_type"), float(liq_result.get("confidence", 0.0)),
            stop_hunt_result.get("direction"), float(stop_hunt_result.get("confidence", 0.0)),
            imbalance_result.get("event_type"), float(imbalance_result.get("confidence", 0.0)),
            features.get("oi_change_1m_pct", 0.0),
            features.get("volume_spike_ratio", 1.0),
            features.get("price_impulse_atr", 0.0),
            features.get("trade_velocity", 0.0),
            features.get("absorption_signal", False),
        )
        return state

    @staticmethod
    def _null_state() -> Dict[str, Any]:
        return {
            "liquidation": {
                "event_type": None, "confidence": 0.0,
                "oi_drop_pct": 0.0, "min_oi_drop_usd": 0.0,
            },
            "stop_hunt": {
                "detected": False, "direction": "NONE",
                "confidence": 0.0, "hunt_low": None, "hunt_high": None,
            },
            "imbalance": {
                "event_type": None, "confidence": 0.0, "direction": "NONE",
            },
            "max_confidence": 0.0,
        }
