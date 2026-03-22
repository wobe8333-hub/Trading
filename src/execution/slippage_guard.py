from __future__ import annotations

import logging
import math
from typing import Any, Dict, Tuple

from src.core.execution_cost_guard.slippage_predictor import SlippagePredictor

logger = logging.getLogger("execution.slippage_guard")

_SLIPPAGE_MAX_BPS = 15.0   # [초기값] 슬리피지 상한 — 초과 시 차단


def _safe(val: Any, default: float = 0.0) -> float:
    try:
        v = float(val)
        return v if math.isfinite(v) else default
    except (TypeError, ValueError):
        return default


class SlippageGuard:
    """
    예상 슬리피지 검사 게이트.
    SlippagePredictor.predict() 결과가 15bps 초과이면 차단.
    """

    def __init__(self) -> None:
        self._predictor = SlippagePredictor()

    def is_slippage_ok(
        self,
        symbol:         str,
        order_size_usd: float,
        market_state:   Dict[str, Any],
        regime:         str,
    ) -> Tuple[bool, str]:
        """
        반환: (True, "OK") / (False, "SLIPPAGE_TOO_HIGH: N.Nbps")
        예외 발생 시 (True, "guard_error") — 시스템 중단 없음.
        """
        try:
            predicted = self._predictor.predict(
                order_size_usd, market_state, regime
            )
            if predicted > _SLIPPAGE_MAX_BPS:    # [초기값]
                reason = f"SLIPPAGE_TOO_HIGH: {predicted:.2f}bps"
                logger.info("slippage_guard blocked symbol=%s %s", symbol, reason)
                return False, reason
            return True, "OK"
        except Exception as exc:
            logger.error("slippage_guard failed symbol=%s error=%s", symbol, exc)
            return True, "guard_error"
