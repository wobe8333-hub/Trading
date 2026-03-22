from __future__ import annotations

import logging
import math
from typing import Any, Dict, Tuple

logger = logging.getLogger("execution.orderbook_guard")

_DEPTH_MIN_USD = 50_000.0   # [검증값] 최소 호가창 깊이


def _safe(val: Any, default: float = 0.0) -> float:
    try:
        v = float(val)
        return v if math.isfinite(v) else default
    except (TypeError, ValueError):
        return default


class OrderbookGuard:
    """
    호가창 깊이 검사 게이트.
    orderbook_depth_usd < 50,000 이면 차단.
    """

    def is_depth_ok(
        self,
        symbol:       str,
        market_state: Dict[str, Any],
    ) -> Tuple[bool, str]:
        """
        반환: (True, "OK") / (False, "DEPTH_TOO_LOW: $N")
        예외 발생 시 (True, "guard_error") — 시스템 중단 없음.
        """
        try:
            depth = _safe(market_state.get("orderbook_depth_usd"), _DEPTH_MIN_USD)
            if depth < _DEPTH_MIN_USD:       # [검증값]
                reason = f"DEPTH_TOO_LOW: ${depth:.0f}"
                logger.info("orderbook_guard blocked symbol=%s %s", symbol, reason)
                return False, reason
            return True, "OK"
        except Exception as exc:
            logger.error("orderbook_guard failed symbol=%s error=%s", symbol, exc)
            return True, "guard_error"
