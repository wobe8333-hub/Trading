from __future__ import annotations

import logging
import math
import random
import time
import uuid
from typing import Any, Dict, Optional

logger = logging.getLogger("execution.order_router")

# ── 주문 타입 결정 임계값 ─────────────────────────────────────
_SPREAD_HOLD_BPS = 6.0      # [초기값] 스프레드 > 6bps → HOLD
_DEPTH_HOLD_USD = 50_000   # [검증값] depth < $50K → HOLD

# ── Mock 슬리피지 시뮬레이션 ──────────────────────────────────
_MOCK_SLIPPAGE_BPS = 0.5      # [초기값] paper_mode mock 슬리피지


def _safe(val: Any, default: float = 0.0) -> float:
    try:
        v = float(val)
        return v if math.isfinite(v) else default
    except (TypeError, ValueError):
        return default


def _mock_order_response(
    symbol: str,
    side: str,
    qty: float,
    price: Optional[float],
    order_type: str,
) -> Dict[str, Any]:
    """paper_mode 가상 체결 응답."""
    filled = price if price else 0.0
    slip = filled * _MOCK_SLIPPAGE_BPS / 10_000
    if side == "Buy":
        filled_price = filled + slip
    else:
        filled_price = max(filled - slip, 0.0)

    return {
        "order_id": str(uuid.uuid4())[:8],
        "symbol": symbol,
        "side": side,
        "qty": qty,
        "price": price,
        "filled_price": round(filled_price, 8),
        "order_type": order_type,
        "status": "Filled",
        "timestamp": time.time(),
        "paper_mode": True,
    }


class OrderRouter:
    """
    주문 타입 결정 + 주문 실행.

    decide_order_type() 로직:
      spread_bps > 6.0  → "HOLD"  (비정상 시장)
      depth_usd  < 50K  → "HOLD"  (유동성 부족)
      그 외             → "LIMIT" (항상 Maker 주문, 70%+ 원칙)
    """

    def __init__(
        self,
        paper_mode: bool = True,
        http_client: Any = None,
    ) -> None:
        self._paper_mode = paper_mode
        self._http_client = http_client

    def decide_order_type(
        self,
        symbol: str,
        market_state: Dict[str, Any],
    ) -> str:
        spread = _safe(market_state.get("spread_bps"), 0.0)
        depth = _safe(market_state.get("orderbook_depth_usd"), _DEPTH_HOLD_USD)

        if spread > _SPREAD_HOLD_BPS:    # [초기값] 6bps 초과 → HOLD
            logger.info(
                "order_router HOLD symbol=%s reason=SPREAD_HIGH spread_bps=%.4f max=%.1f",
                symbol, spread, _SPREAD_HOLD_BPS,
            )
            return "HOLD"
        if depth < _DEPTH_HOLD_USD:      # [검증값] depth 부족 → HOLD
            logger.info(
                "order_router HOLD symbol=%s reason=DEPTH_LOW depth_usd=%.0f min=%.0f",
                symbol, depth, _DEPTH_HOLD_USD,
            )
            return "HOLD"
        logger.info(
            "order_router LIMIT symbol=%s spread_bps=%.4f depth_usd=%.0f",
            symbol, spread, depth,
        )
        return "LIMIT"                   # [검증값] 항상 LIMIT (Maker 70%+ 원칙)

    def place_order(
        self,
        symbol: str,
        side: str,
        qty: float,
        price: Optional[float],
        order_type: str,
        reduce_only: bool = False,
    ) -> Dict[str, Any]:
        """
        주문 실행.
        paper_mode=True → mock 체결 반환 (API 호출 없음).
        """
        try:
            if self._paper_mode:
                return _mock_order_response(symbol, side, qty, price, order_type)

            params: Dict[str, Any] = {
                "category": "linear",
                "symbol": symbol,
                "side": side,
                "orderType": "Market" if order_type == "MARKET" else "Limit",
                "qty": str(qty),
                "timeInForce": "GTC" if order_type == "LIMIT" else "IOC",
            }
            if price:
                params["price"] = str(price)
            if reduce_only:
                params["reduceOnly"] = True

            response = self._http_client.place_order(**params)
            return response

        except Exception as exc:
            logger.error(
                "order_router place_order failed symbol=%s error=%s",
                symbol, exc,
            )
            return {"status": "Error", "error": str(exc), "paper_mode": self._paper_mode}
