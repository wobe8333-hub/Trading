from __future__ import annotations

import logging
import math
from typing import Any, Dict, Tuple

logger = logging.getLogger("execution.spread_guard")

_SPREAD_MAX_BPS = 6.0   # [초기값] 스프레드 상한 — 초과 시 차단


def _safe(val: Any, default: float = 0.0) -> float:
    try:
        v = float(val)
        return v if math.isfinite(v) else default
    except (TypeError, ValueError):
        return default


class SpreadGuard:
    """
    스프레드 검사 게이트.
    spread_bps > 6.0 이면 차단.
    """

    def is_spread_ok(
        self,
        symbol:       str,
        market_state: Dict[str, Any],
    ) -> Tuple[bool, str]:
        """
        반환: (True, "OK") / (False, "SPREAD_TOO_WIDE: N.Nbps")
        예외 발생 시 (True, "guard_error") — 시스템 중단 없음.
        """
        try:
            spread = _safe(market_state.get("spread_bps"), 0.0)
            if spread > _SPREAD_MAX_BPS:     # [초기값]
                reason = f"SPREAD_TOO_WIDE: {spread:.2f}bps"
                logger.info("spread_guard blocked symbol=%s %s", symbol, reason)
                return False, reason
            return True, "OK"
        except Exception as exc:
            logger.error("spread_guard failed symbol=%s error=%s", symbol, exc)
            return True, "guard_error"
