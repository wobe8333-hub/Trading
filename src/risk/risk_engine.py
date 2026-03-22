from __future__ import annotations

import logging
from typing import Any, Dict, Tuple

from src.risk.kill_switch import KillSwitch
from src.risk.daily_loss_guard import DailyLossGuard
from src.risk.streak_guard import StreakGuard

logger = logging.getLogger("risk.engine")

_SPREAD_ANOMALY_BPS = 100.0  # [검증값] spread > 100bps → SPREAD_ANOMALY
_SLIPPAGE_ANOMALY = 5.0  # [검증값] slippage > 5bps → SLIPPAGE_ANOMALY


class RiskEngine:
    """
    진입 전(pre-trade) + 체결 후(post-trade) 통합 리스크 검사.

    check_pre_trade():
      1. kill_switch.is_blocked()
      2. kill_switch.is_symbol_blocked()
      3. kill_switch.is_regime_blocked()
      4. daily_loss_guard.check()
      5. spread 이상 감지

    check_post_trade():
      1. streak_guard.record_trade()
      2. streak_guard.check()
      3. slippage 이상 감지
    """

    def __init__(self) -> None:
        self.kill_switch = KillSwitch()
        self._daily_guard = DailyLossGuard(self.kill_switch)
        self._streak = StreakGuard(self.kill_switch)

    def check_pre_trade(
        self,
        symbol: str,
        regime: str,
        daily_pnl: float,
        stage: Dict[str, Any],
        market_state: Dict[str, Any],
    ) -> Tuple[bool, str]:
        """
        반환: (True, "OK") / (False, reason)
        예외 발생 시 (True, "check_error") — 시스템 중단 없음.
        """
        try:
            if self.kill_switch.is_blocked():
                return False, f"KILL_SWITCH_ACTIVE: {self.kill_switch.reason}"

            if self.kill_switch.is_symbol_blocked(symbol):
                return False, f"SYMBOL_BLOCKED: {symbol}"

            if self.kill_switch.is_regime_blocked(regime):
                return False, f"REGIME_BLOCKED: {regime}"

            ok, reason = self._daily_guard.check(daily_pnl, stage)
            if not ok:
                return False, reason

            spread = float(market_state.get("spread_bps", 0.0))
            if spread > _SPREAD_ANOMALY_BPS:  # [검증값]
                self.kill_switch.trigger("SPREAD_ANOMALY")
                return False, f"SPREAD_ANOMALY: {spread:.1f}bps"

            return True, "OK"
        except Exception as exc:
            logger.error("risk_engine check_pre_trade failed error=%s", exc)
            return True, "check_error"

    def check_post_trade(
        self,
        symbol: str,
        regime: str,
        pnl_net: float,
        slippage_bps: float,
    ) -> None:
        """체결 후 streak 기록 + slippage 이상 감지."""
        try:
            self._streak.record_trade(pnl_net, symbol, regime)
            self._streak.check()

            if slippage_bps > _SLIPPAGE_ANOMALY:  # [검증값]
                self.kill_switch.trigger("SLIPPAGE_ANOMALY")
                logger.warning(
                    "risk_engine SLIPPAGE_ANOMALY slippage=%.2f",
                    slippage_bps,
                )
        except Exception as exc:
            logger.error("risk_engine check_post_trade failed error=%s", exc)

    def reset_daily(self) -> None:
        self._streak.reset()

