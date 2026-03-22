from __future__ import annotations

import logging
from typing import Any, Dict, Tuple

from src.risk.kill_switch import KillSwitch

logger = logging.getLogger("risk.daily_loss_guard")


class DailyLossGuard:
    """
    일일 손실 한도 초과 시 Kill Switch 발동.
    daily_pnl <= stage['daily_loss_limit'] → DAILY_LOSS_LIMIT 트리거
    """

    def __init__(self, kill_switch: KillSwitch) -> None:
        self._ks = kill_switch

    def check(
        self,
        daily_pnl: float,
        stage: Dict[str, Any],
    ) -> Tuple[bool, str]:
        """
        반환: (True, "OK") / (False, "DAILY_LOSS_LIMIT exceeded")
        예외 발생 시 (True, "guard_error") — 시스템 중단 없음.
        """
        try:
            limit = float(stage.get("daily_loss_limit", -35))
            if daily_pnl <= limit:
                self._ks.trigger("DAILY_LOSS_LIMIT", cooldown_hours=0.0)
                reason = (
                    f"DAILY_LOSS_LIMIT exceeded: "
                    f"{daily_pnl:.2f} <= {limit:.2f}"
                )
                logger.warning("daily_loss_guard BLOCKED %s", reason)
                return False, reason
            return True, "OK"
        except Exception as exc:
            logger.error("daily_loss_guard check failed error=%s", exc)
            return True, "guard_error"

