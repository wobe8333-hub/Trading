from __future__ import annotations

import logging
from collections import defaultdict
from typing import Tuple

from src.risk.kill_switch import KillSwitch

logger = logging.getLogger("risk.streak_guard")

_CONSEC_LOSS_TRIGGER = 3  # [검증값] 연속 손실 3회 → kill_switch
_SYMBOL_LOSS_TRIGGER = 2  # [검증값] 동일 symbol 2회 → symbol 차단 2시간
_REGIME_LOSS_TRIGGER = 2  # [검증값] 동일 regime 2회 → regime 차단 1시간


class StreakGuard:
    """
    연속 손실 / 동일 symbol·regime 반복 손실 감지.
    """

    def __init__(self, kill_switch: KillSwitch) -> None:
        self._ks = kill_switch
        self.consecutive_losses: int = 0
        self.last_symbol: str = ""
        self.last_regime: str = ""
        self.symbol_loss_count = defaultdict(int)
        self.regime_loss_count = defaultdict(int)

    def record_trade(self, pnl_net: float, symbol: str, regime: str) -> None:
        """거래 결과 기록."""
        if pnl_net < 0:
            self.consecutive_losses += 1
            self.symbol_loss_count[symbol] += 1
            self.regime_loss_count[regime] += 1
        else:
            # 이익 거래 → 연속 손실 리셋
            self.consecutive_losses = 0
        self.last_symbol = symbol
        self.last_regime = regime

    def check(self) -> Tuple[bool, str]:
        """
        반환: (True, "OK") / (False, reason)
        """
        try:
            if self.consecutive_losses >= _CONSEC_LOSS_TRIGGER:  # [검증값]
                self._ks.trigger("CONSECUTIVE_LOSSES", cooldown_hours=1.0)
                return False, f"CONSECUTIVE_LOSSES: {self.consecutive_losses}"

            # 동일 symbol 2회 연속 손실 → 2시간 차단
            if (
                self.last_symbol
                and self.symbol_loss_count[self.last_symbol] >= _SYMBOL_LOSS_TRIGGER
            ):  # [검증값]
                self._ks.block_symbol(self.last_symbol, hours=2.0)

            # 동일 regime 2회 연속 손실 → 1시간 차단
            if (
                self.last_regime
                and self.regime_loss_count[self.last_regime] >= _REGIME_LOSS_TRIGGER
            ):  # [검증값]
                self._ks.block_regime(self.last_regime, hours=1.0)

            return True, "OK"
        except Exception as exc:
            logger.error("streak_guard check failed error=%s", exc)
            return True, "guard_error"

    def reset(self) -> None:
        """일일 리셋."""
        self.consecutive_losses = 0
        self.symbol_loss_count.clear()
        self.regime_loss_count.clear()

