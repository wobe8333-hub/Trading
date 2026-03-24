from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Dict

from src.core.market_data.symbol_metadata import SymbolMetadata
from src.execution.order_router import OrderRouter

logger = logging.getLogger("execution.bracket_order_manager")


def _round_qty(symbol: str, qty: float) -> float:
    return round(qty, 3)


class BracketOrderManager:
    """
    Bracket 주문 관리자.
    TP1 (LIMIT) + Stop Loss (Market SL) 동시 등록.
    TP2는 TP1 체결 후 잔여 수량으로 처리 (pending).
    """

    def __init__(
        self,
        order_router: OrderRouter,
        paper_mode: bool = True,
        http_client: Any = None,
    ) -> None:
        self._router = order_router
        self._paper_mode = paper_mode
        self._http_client = http_client

    def place_bracket(
        self,
        symbol: str,
        side: str,          # "Buy" / "Sell"
        qty: float,
        entry_price: float,
        stop_price: float,
        tp1_price: float,
        tp2_price: float,
        tp1_qty_ratio: float,       # TP1에서 청산할 비율
    ) -> Dict[str, Any]:
        """
        구현지침서 명세:
        tp1_qty  = round_qty(qty * tp1_qty_ratio)
        tp2_qty  = round_qty(qty - tp1_qty)
        close_side = "Sell" if side == "Buy" else "Buy"
        TP1: LIMIT reduce_only
        SL:  Market stopLoss (paper_mode에서는 mock)
        반환: {"tp1": tp1_order, "sl": sl_order, "tp2_pending": tp2_price}
        """
        try:
            return self._place(
                symbol, side, qty, entry_price,
                stop_price, tp1_price, tp2_price, tp1_qty_ratio,
            )
        except Exception as exc:
            logger.error(
                "bracket_order_manager place_bracket failed symbol=%s error=%s",
                symbol, exc,
            )
            return {
                "tp1": {"status": "Error"},
                "sl": {"status": "Error"},
                "tp2_pending": tp2_price,
                "error": str(exc),
            }

    def _place(
        self,
        symbol: str,
        side: str,
        qty: float,
        entry_price: float,
        stop_price: float,
        tp1_price: float,
        tp2_price: float,
        tp1_qty_ratio: float,
    ) -> Dict[str, Any]:
        tp1_qty = _round_qty(symbol, qty * tp1_qty_ratio)
        tp2_qty = _round_qty(symbol, qty - tp1_qty)
        close_side = "Sell" if side == "Buy" else "Buy"

        # ── TP1 주문 (LIMIT reduce_only) ─────────────────────
        tp1_order = self._router.place_order(
            symbol=symbol, side=close_side, qty=tp1_qty,
            price=tp1_price, order_type="LIMIT", reduce_only=True,
        )

        # ── SL 주문 ──────────────────────────────────────────
        if self._paper_mode:
            sl_order = {
                "order_id": str(uuid.uuid4())[:8],
                "symbol": symbol,
                "side": close_side,
                "qty": qty,
                "stop_price": stop_price,
                "order_type": "STOP_MARKET",
                "status": "Registered",
                "timestamp": time.time(),
                "paper_mode": True,
            }
        else:
            sl_order = self._http_client.place_order(
                category="linear",
                symbol=symbol,
                side=close_side,
                orderType="Market",
                qty=str(qty),
                stopLoss=str(stop_price),
                slTriggerBy="LastPrice",
                reduceOnly=True,
            )
        if self._paper_mode:
            tp2_order = {
                "order_id": str(uuid.uuid4())[:8],
                "symbol": symbol,
                "side": close_side,
                "qty": tp2_qty,
                "price": tp2_price,
                "order_type": "LIMIT",
                "status": "Registered",
                "timestamp": time.time(),
                "paper_mode": True,
            }
        else:
            tp2_order = self._router.place_order(
                symbol=symbol, side=close_side, qty=tp2_qty,
                price=tp2_price, order_type="LIMIT", reduce_only=True,
            )

        logger.info(
            "bracket_order_manager placed symbol=%s tp1_qty=%.3f tp2_qty=%.3f sl=%.2f tp1=%.2f",
            symbol, tp1_qty, tp2_qty, stop_price, tp1_price,
        )

        return {"tp1": tp1_order, "sl": sl_order, "tp2": tp2_order}

    def verify_sl_registered(
        self,
        symbol: str,
    ) -> bool:
        """
        SL 등록 여부 확인.
        paper_mode → 항상 True.
        실거래 → stopLoss 필드 "0" 또는 "" 이면 False.
        """
        if self._paper_mode:
            return True
        try:
            response = self._http_client.get_positions(
                category="linear", symbol=symbol
            )
            positions = response.get("result", {}).get("list", [])
            for pos in positions:
                sl = pos.get("stopLoss", "0")
                if sl in ("0", "", None):
                    logger.warning(
                        "bracket_order_manager SL not registered symbol=%s",
                        symbol,
                    )
                    return False
            return True
        except Exception as exc:
            logger.error(
                "bracket_order_manager verify_sl failed symbol=%s error=%s",
                symbol, exc,
            )
            return False
