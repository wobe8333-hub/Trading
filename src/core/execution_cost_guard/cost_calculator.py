from __future__ import annotations

import logging
import math
from typing import Any, Dict

from src.core.execution_cost_guard.slippage_predictor import SlippagePredictor

logger = logging.getLogger("cost_guard.calculator")

# ── 수수료 기준값 (명목가치 기준, 레버리지 무관) ──────────────
_MAKER_FEE_BPS  = 4.0    # [검증값] 0.02% * 2 (진입 + 청산) = 0.04% = 4bps
_TAKER_FEE_BPS  = 11.0   # [검증값] 0.055% * 2 = 0.11% = 11bps
_MAKER_FEE_RATE = 0.8    # [검증값] 구현지침서 표기값 (참고용)
_TAKER_FEE_RATE = 2.2    # [검증값] 구현지침서 표기값 (참고용)

_MAX_COST_RATIO = 0.20   # [검증값] TP1 대비 비용 최대 20%


def _safe(val: Any, default: float = 0.0) -> float:
    try:
        v = float(val)
        return v if math.isfinite(v) else default
    except (TypeError, ValueError):
        return default


class CostCalculator:
    """
    총 실행 비용(bps) 계산기.

    compute_total_cost_bps() 반환:
    {
      "spread_cost_bps": float,
      "slippage_bps":    float,
      "fee_bps":         float,
      "total_cost_bps":  float,
      "maker_fee_bps":   0.8,    # [검증값] 참고용
      "taker_fee_bps":   2.2,    # [검증값] 참고용
    }
    """

    def compute_total_cost_bps(
        self,
        symbol:         str,
        order_type:     str,         # "MARKET" or "LIMIT"
        order_size_usd: float,
        market_state:   Dict[str, Any],
        regime:         str,
    ) -> Dict[str, Any]:
        try:
            return self._compute(
                symbol, order_type, order_size_usd, market_state, regime
            )
        except Exception as exc:
            logger.error(
                "cost_calculator compute failed symbol=%s error=%s",
                symbol, exc,
            )
            return self._error_result()

    def _compute(
        self,
        symbol:         str,
        order_type:     str,
        order_size_usd: float,
        market_state:   Dict[str, Any],
        regime:         str,
    ) -> Dict[str, Any]:
        # ── fee_bps 계산 ──────────────────────────────────────
        if order_type == "LIMIT":
            fee_bps = _MAKER_FEE_BPS   # [검증값] 4bps
        else:
            fee_bps = _TAKER_FEE_BPS   # [검증값] 11bps

        # ── spread_cost_bps ───────────────────────────────────
        spread_bps      = _safe(market_state.get("spread_bps"), 0.0)
        spread_cost_bps = spread_bps * 0.5   # [검증값] 편도 스프레드 절반

        # ── slippage_bps ──────────────────────────────────────
        slippage_bps = SlippagePredictor.predict(
            order_size_usd, market_state, regime
        )

        # ── 총합 ──────────────────────────────────────────────
        total_cost_bps = spread_cost_bps + slippage_bps + fee_bps

        result = {
            "spread_cost_bps": round(spread_cost_bps, 4),
            "slippage_bps":    round(slippage_bps,    4),
            "fee_bps":         round(fee_bps,         4),
            "total_cost_bps":  round(total_cost_bps,  4),
            "maker_fee_bps":   _MAKER_FEE_RATE,   # [검증값] 참고용
            "taker_fee_bps":   _TAKER_FEE_RATE,   # [검증값] 참고용
        }
        logger.info(
            "cost_calculator symbol=%s "
            "total=%.4fbps spread=%.4f slip=%.4f fee=%.4f order_type=%s",
            symbol, total_cost_bps, spread_cost_bps, slippage_bps, fee_bps,
            order_type,
        )
        return result

    @staticmethod
    def is_cost_acceptable(
        total_cost_bps:   float,
        tp1_distance_bps: float,
    ) -> bool:
        """
        total_cost_bps <= tp1_distance_bps * 0.20 이면 True.
        tp1_distance_bps 가 0이면 차단(False).
        """
        if tp1_distance_bps <= 0:
            return False
        return total_cost_bps <= tp1_distance_bps * _MAX_COST_RATIO  # [검증값]

    @staticmethod
    def _error_result() -> Dict[str, Any]:
        return {
            "spread_cost_bps": 0.0,
            "slippage_bps":    99.0,
            "fee_bps":         99.0,
            "total_cost_bps":  999.0,
            "maker_fee_bps":   _MAKER_FEE_RATE,
            "taker_fee_bps":   _TAKER_FEE_RATE,
        }

