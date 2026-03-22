from __future__ import annotations

import logging
import math
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger("strategy.base")

# ATR 배수 기본값 (system_config.yaml에서 읽어야 하나 BaseStrategy는 strategy_config 기반)
# 아래 값은 system_config.yaml의 stop_atr_*, tp1_atr_*, tp2_atr_* 값을 반영
_STOP_ATR = {"TREND_UP": 0.8, "TREND_DOWN": 0.8, "RANGE": 0.6, "EXPANSION": 0.9}   # [초기값]
_TP1_ATR  = {"TREND_UP": 1.2, "TREND_DOWN": 1.2, "RANGE": 1.0, "EXPANSION": 1.5}   # [초기값]
_TP2_ATR  = {"TREND_UP": 2.0, "TREND_DOWN": 2.0, "RANGE": 1.4, "EXPANSION": 2.2}   # [초기값]
_TP1_CLOSE_RATIO = {"TREND_UP": 0.5, "TREND_DOWN": 0.5, "RANGE": 0.6, "EXPANSION": 0.4}


_NULL_LAYER_HIT: Dict[str, Any] = {
    "layer1": False, "layer2": False, "layer3": False, "direction": None
}


class BaseStrategy:
    """
    6개 전략의 공통 베이스 클래스.

    - config: strategy_config.yaml 내 해당 전략 딕셔너리
    - params: config["params"] 딕셔너리 (하드코딩 금지, yaml 참조)
    """

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config
        self.params = config.get("params", {})

    def is_allowed(self, macro_state: str, regime: str) -> bool:
        """
        구현지침서 명세:
        1. forbidden_regimes 포함 → False
        2. allowed_regimes 미포함 → False
        3. macro_state == RISK_OFF → False
        4. 그 외 → True
        """
        if regime in self.config.get("forbidden_regimes", []):
            return False
        if regime not in self.config.get("allowed_regimes", []):
            return False
        if macro_state == "RISK_OFF":
            return False
        return True

    def generate_signal(
        self,
        symbol:          str,
        market_state:    Dict[str, Any],
        orderflow_state: Dict[str, Any],
        direction:       Optional[str] = None,
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        반환: (signal: bool, layer_hit: dict)
        layer_hit = {"layer1": bool, "layer2": bool, "layer3": bool, "direction": str|None}
        """
        raise NotImplementedError

    def compute_stop(
        self,
        entry_price: float,
        atr:         float,
        regime:      str,
        direction:   str,
    ) -> float:
        """ATR 기반 Stop Loss 가격 계산."""
        mult = _STOP_ATR.get(regime, 0.8)   # [초기값]
        if direction == "LONG":
            return entry_price - atr * mult
        return entry_price + atr * mult

    def compute_targets(
        self,
        entry_price: float,
        atr:         float,
        regime:      str,
        direction:   str,
    ) -> Tuple[float, float]:
        """ATR 기반 TP1, TP2 가격 계산. 반환: (tp1, tp2)."""
        mult1 = _TP1_ATR.get(regime, 1.2)   # [초기값]
        mult2 = _TP2_ATR.get(regime, 2.0)   # [초기값]
        if direction == "LONG":
            return entry_price + atr * mult1, entry_price + atr * mult2
        return entry_price - atr * mult1, entry_price - atr * mult2

    def validate_rr(
        self,
        entry: float,
        stop:  float,
        tp1:   float,
    ) -> Tuple[bool, float]:
        """
        구현지침서 명세:
        risk   = abs(entry - stop)
        reward = abs(tp1 - entry)
        rr     = reward / risk
        return rr >= self.config["min_rr"], rr
        """
        risk = abs(entry - stop)
        reward = abs(tp1 - entry)
        if risk < 1e-9:
            return False, 0.0
        rr = reward / risk
        return rr >= self.config.get("min_rr", 1.3), round(rr, 4)

    def get_tp1_close_ratio(self, regime: str) -> float:
        return _TP1_CLOSE_RATIO.get(regime, 0.5)

    def metadata(self) -> Dict[str, Any]:
        return {
            "name": self.__class__.__name__,
            "allowed_regimes": self.config.get("allowed_regimes", []),
            "forbidden_regimes": self.config.get("forbidden_regimes", []),
            "preferred_macro": self.config.get("preferred_macro", []),
            "preferred_coin_types": self.config.get("preferred_coin_types", []),
            "min_entry_score": self.config.get("min_entry_score", 70),
            "min_rr": self.config.get("min_rr", 1.3),
            "params": self.params,
        }

    @staticmethod
    def _null_hit() -> Dict[str, Any]:
        return dict(_NULL_LAYER_HIT)

