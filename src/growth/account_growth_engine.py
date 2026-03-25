from __future__ import annotations

import logging
from typing import Any, Dict

from src.growth.stage_manager import StageManager
from src.growth.profit_lock_manager import ProfitLockManager

logger = logging.getLogger("growth.account_growth_engine")


class AccountGrowthEngine:
    """
    Stage 자동 전환 + Profit Lock 통합 관리.

    get_trade_parameters() 반환:
    {
      "stage_id": int,
      "risk_pct": float,
      "daily_loss_limit": float,
      "scale_limit": float,   # profit_lock 반영
      "min_entry_score": int, # profit_lock 반영
      "is_halted": bool,
      "conservative_mode": bool,
    }
    """

    def __init__(self) -> None:
        self._stage_mgr = StageManager()
        self._profit_lock = ProfitLockManager()

    def get_trade_parameters(
        self,
        equity: float,
        daily_pnl: float,
    ) -> Dict[str, Any]:
        """
        구현지침서 명세:
        stage        = stage_manager.get_current_stage(equity)
        profit_lock  = profit_lock_manager.check_profit_lock(daily_pnl, stage["id"])
        반환 통합
        """
        try:
            stage = self._stage_mgr.get_current_stage(equity)
            stage_id = int(stage.get("id", 1))
            risk_pct = float(stage.get("risk_pct_per_trade", 0.032))
            daily_limit = float(stage.get("daily_loss_limit", -35))
            profit_locks = stage.get("profit_locks", [])

            lock = self._profit_lock.check_profit_lock(
                daily_pnl, stage_id, profit_locks
            )

            result = {
                "stage_id": stage_id,
                "risk_pct": risk_pct,
                "daily_loss_limit": daily_limit,
                "scale_limit": lock["scale_limit"],
                "min_entry_score": lock["min_entry_score"],
                "is_halted": lock["halt"],
                "conservative_mode": lock["conservative_mode"],
            }

            logger.info(
                "account_growth_engine equity=%.2f stage=%d "
                "risk=%.4f scale=%.2f halted=%s "
                "daily_pnl=%.4f daily_limit=%.2f "
                "min_score=%d conservative=%s",
                equity, stage_id,
                risk_pct, lock["scale_limit"], lock["halt"],
                daily_pnl, daily_limit,
                lock["min_entry_score"], lock["conservative_mode"],
            )
            return result

        except Exception as exc:
            logger.error(
                "account_growth_engine get_trade_parameters failed error=%s", exc
            )
            return {
                "stage_id": 1,
                "risk_pct": 0.032,
                "daily_loss_limit": -35.0,
                "scale_limit": 1.0,
                "min_entry_score": 70,
                "is_halted": False,
                "conservative_mode": False,
            }

    def update_daily_pnl(self, pnl_net: float) -> None:
        self._profit_lock.update_daily_pnl(pnl_net)

    def reset_daily(self) -> None:
        self._profit_lock.reset_daily()

    def check_stage_transition(
        self,
        prev_equity: float,
        curr_equity: float,
    ) -> Dict[str, Any]:
        return self._stage_mgr.check_stage_transition(prev_equity, curr_equity)

