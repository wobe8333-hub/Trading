from __future__ import annotations

import logging
import math
from typing import Any, Dict

logger = logging.getLogger("cost_guard.slippage")

# ── impact_factor 매핑 ───────────────────────────────────────
_IMPACT_FACTOR: Dict[str, float] = {
    "EXPANSION":  2.5,   # [초기값]
    "TREND_UP":   1.5,   # [초기값]
    "TREND_DOWN": 1.5,   # [초기값]
    "RANGE":      1.0,   # [초기값]
}
_SLIPPAGE_CAP_BPS = 20.0  # [초기값] 최대 20bps 캡


def _safe(val: Any, default: float = 0.0) -> float:
    try:
        v = float(val)
        return v if math.isfinite(v) else default
    except (TypeError, ValueError):
        return default


class SlippagePredictor:
    """
    주문 규모 + 호가창 depth + Regime → 예상 슬리피지(bps) 산출.

    공식 (구현지침서 명세):
      slippage = (order_size_usd / depth_1pct_usd) * 100 * impact_factor
      return min(slippage, 20)  # 최대 20bps 캡
    """

    @staticmethod
    def predict(
        order_size_usd: float,
        market_state:   Dict[str, Any],
        regime:         str,
    ) -> float:
        """
        슬리피지 예측값(bps) 반환.
        depth_1pct_usd 가 0이거나 없으면 보수적으로 최대값 반환.
        """
        try:
            depth_1pct = _safe(
                market_state.get("orderbook_depth_usd"), 0.0
            )
            impact = _IMPACT_FACTOR.get(regime, 1.5)  # [초기값] 기본 1.5

            if depth_1pct <= 0:
                # depth 정보 없음 → 보수적 최대값
                return _SLIPPAGE_CAP_BPS

            slippage = (order_size_usd / depth_1pct) * 100.0 * impact
            result   = min(slippage, _SLIPPAGE_CAP_BPS)
            logger.debug(
                "slippage_predictor regime=%s size=%.1f depth=%.1f slippage=%.2fbps",
                regime, order_size_usd, depth_1pct, result,
            )
            return round(result, 4)
        except Exception as exc:
            logger.error("slippage_predictor failed error=%s", exc)
            return _SLIPPAGE_CAP_BPS

