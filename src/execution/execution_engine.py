from __future__ import annotations

import logging
import math
import time
import uuid
from typing import Any, Dict, Optional

from src.execution.order_router import OrderRouter
from src.execution.bracket_order_manager import BracketOrderManager
from src.execution.spread_guard import SpreadGuard
from src.execution.orderbook_guard import OrderbookGuard
from src.execution.slippage_guard import SlippageGuard

logger = logging.getLogger("execution.engine")

# ── 수수료율 ──────────────────────────────────────────────────
_MAKER_FEE_RATE = 0.0002    # [검증값] Limit  0.02%
_TAKER_FEE_RATE = 0.00055   # [검증값] Market 0.055%


def _safe(val: Any, default: float = 0.0) -> float:
    try:
        v = float(val)
        return v if math.isfinite(v) else default
    except (TypeError, ValueError):
        return default


class ExecutionEngine:
    """
    실행 엔진 — 주문 실행 전체 파이프라인.

    실행 흐름 (구현지침서 명세):
    1. spread_guard.is_spread_ok()
    2. orderbook_guard.is_depth_ok()
    3. slippage_guard.is_slippage_ok()
    4. order_router.decide_order_type()
    5. 실제 수량 계산 (contracts * scale)
    6. order_router.place_order()
    7. bracket_order_manager.place_bracket()
    8. bracket_order_manager.verify_sl_registered()
    9. fee_usd 계산
    10. 결과 반환

    paper_mode=True → 실제 API 호출 없이 mock 체결 반환.
    """

    def __init__(
        self,
        paper_mode: bool = True,
        http_client: Any = None,
        market_state_provider: Any = None,
    ) -> None:
        self._paper_mode = paper_mode
        self._router = OrderRouter(paper_mode=paper_mode, http_client=http_client)
        self._bracket = BracketOrderManager(
            order_router=self._router,
            paper_mode=paper_mode,
            http_client=http_client,
        )
        self._spread_guard = SpreadGuard()
        self._ob_guard = OrderbookGuard()
        self._slip_guard = SlippageGuard()
        self._market_state_provider = market_state_provider

    def execute(
        self,
        symbol: str,
        direction: str,       # "LONG" / "SHORT"
        position_scale: float,
        position_size_contracts: float,
        entry_price: float,
        stop_price: float,
        tp1_price: float,
        tp2_price: float,
        tp1_ratio: float,
        regime: str,
        market_state: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        실행 파이프라인.
        예외 발생 시 blocked=True + reason 포함 dict 반환 — 시스템 중단 없음.
        """
        try:
            return self._execute(
                symbol, direction, position_scale,
                position_size_contracts, entry_price,
                stop_price, tp1_price, tp2_price,
                tp1_ratio, regime,
                market_state or {},
            )
        except Exception as exc:
            logger.error(
                "execution_engine execute failed symbol=%s error=%s",
                symbol, exc,
            )
            return self._error_result(symbol, direction, entry_price, str(exc))

    def _execute(
        self,
        symbol: str,
        direction: str,
        position_scale: float,
        position_size_contracts: float,
        entry_price: float,
        stop_price: float,
        tp1_price: float,
        tp2_price: float,
        tp1_ratio: float,
        regime: str,
        market_state: Dict[str, Any],
    ) -> Dict[str, Any]:

        side = "Buy" if direction == "LONG" else "Sell"

        # ── 1. Spread Guard ───────────────────────────────────
        spread_ok, spread_reason = self._spread_guard.is_spread_ok(symbol, market_state)
        if not spread_ok:
            logger.info("execution blocked reason=%s symbol=%s", spread_reason, symbol)
            return self._blocked_result(symbol, direction, entry_price, spread_reason)

        # ── 2. Orderbook Guard ────────────────────────────────
        depth_ok, depth_reason = self._ob_guard.is_depth_ok(symbol, market_state)
        if not depth_ok:
            logger.info("execution blocked reason=%s symbol=%s", depth_reason, symbol)
            return self._blocked_result(symbol, direction, entry_price, depth_reason)

        # ── 3. Slippage Guard ─────────────────────────────────
        order_size_usd = position_size_contracts * position_scale * entry_price
        slip_ok, slip_reason = self._slip_guard.is_slippage_ok(
            symbol, order_size_usd, market_state, regime
        )
        if not slip_ok:
            logger.info("execution blocked reason=%s symbol=%s", slip_reason, symbol)
            return self._blocked_result(symbol, direction, entry_price, slip_reason)

        # ── 4. 주문 타입 결정 ─────────────────────────────────
        order_type = self._router.decide_order_type(symbol, market_state)
        if order_type == "HOLD":
            return self._blocked_result(symbol, direction, entry_price, "ORDER_TYPE_HOLD")

        # ── 5. 실제 수량 계산 ─────────────────────────────────
        qty = round(position_size_contracts * position_scale, 3)
        if qty <= 0:
            return self._blocked_result(symbol, direction, entry_price, "QTY_ZERO")

        # ── 6. 주문 실행 ──────────────────────────────────────
        # paper_mode + MARKET: mock 체결가 시뮬을 위해 entry_price 전달 (실거래는 price 없음)
        if order_type == "LIMIT":
            price_arg = entry_price
        else:
            price_arg = entry_price if self._paper_mode else None
        order_resp = self._router.place_order(
            symbol=symbol, side=side, qty=qty,
            price=price_arg, order_type=order_type,
        )

        filled_price = _safe(order_resp.get("filled_price"), entry_price)

        # ── 7. Bracket 주문 ───────────────────────────────────
        bracket_resp = self._bracket.place_bracket(
            symbol=symbol, side=side, qty=qty,
            entry_price=entry_price,
            stop_price=stop_price,
            tp1_price=tp1_price,
            tp2_price=tp2_price,
            tp1_qty_ratio=tp1_ratio,
        )

        # ── 8. SL 등록 확인 ───────────────────────────────────
        sl_registered = self._bracket.verify_sl_registered(symbol)
        if not sl_registered:
            logger.warning(
                "execution_engine SL not registered — kill_switch signal symbol=%s",
                symbol,
            )

        # ── 9. fee_usd 계산 ───────────────────────────────────
        qty_usd = qty * filled_price
        if order_type == "LIMIT":
            fee_usd = qty_usd * _MAKER_FEE_RATE    # [검증값] 0.02%
        else:
            fee_usd = qty_usd * _TAKER_FEE_RATE    # [검증값] 0.055%

        order_id = order_resp.get("order_id", str(uuid.uuid4())[:8])

        result = {
            "order_id": order_id,
            "symbol": symbol,
            "direction": direction,
            "qty": qty,
            "entry_price": entry_price,
            "filled_price": round(filled_price, 8),
            "order_type": order_type,
            "fee_usd": round(fee_usd, 6),
            "sl_registered": sl_registered,
            "timestamp": time.time(),
            "blocked": False,
            "bracket": bracket_resp,
        }

        logger.info(
            "execution_engine executed symbol=%s dir=%s "
            "qty=%.4f intended=%.5f filled=%.5f "
            "slippage_bps=%.4f fee=%.6f "
            "sl=%s order_type=%s order_id=%s",
            symbol, direction,
            qty, entry_price, filled_price,
            abs(filled_price - entry_price) / entry_price * 10000 if entry_price > 0 else 0.0,
            fee_usd, sl_registered, order_type, order_id,
        )
        return result

    @staticmethod
    def _blocked_result(
        symbol: str,
        direction: str,
        entry: float,
        reason: str,
    ) -> Dict[str, Any]:
        return {
            "order_id": "",
            "symbol": symbol,
            "direction": direction,
            "qty": 0.0,
            "entry_price": entry,
            "filled_price": entry,
            "order_type": "BLOCKED",
            "fee_usd": 0.0,
            "sl_registered": False,
            "timestamp": time.time(),
            "blocked": True,
            "reason": reason,
        }

    @staticmethod
    def _error_result(
        symbol: str,
        direction: str,
        entry: float,
        error: str,
    ) -> Dict[str, Any]:
        return {
            "order_id": "",
            "symbol": symbol,
            "direction": direction,
            "qty": 0.0,
            "entry_price": entry,
            "filled_price": entry,
            "order_type": "ERROR",
            "fee_usd": 0.0,
            "sl_registered": False,
            "timestamp": time.time(),
            "blocked": True,
            "reason": f"EXCEPTION: {error}",
        }
