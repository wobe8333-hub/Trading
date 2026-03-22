from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("growth.profit_lock_manager")

_DEFAULT_LOCK_STATE = {
    "halt": False,
    "scale_limit": 1.0,
    "min_entry_score": 70,
    "conservative_mode": False,
}


class ProfitLockManager:
    """
    일일 수익 기반 Profit Lock 관리.

    check_profit_lock():
      profit_locks 리스트를 threshold 내림차순 정렬 후
      daily_pnl >= threshold 인 최초 lock 적용.

    내부 상태:
      daily_start_equity: float
      daily_pnl_net: float
      is_halted: bool
      current_scale_limit: float
    """

    def __init__(self) -> None:
        self.daily_start_equity: float = 0.0
        self.daily_pnl_net: float = 0.0
        self.is_halted: bool = False
        self.current_scale_limit: float = 1.0

    def check_profit_lock(
        self,
        daily_pnl: float,
        stage_id: int,
        profit_locks: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """
        구현지침서 명세:
        profit_locks 순회 → threshold 도달 여부 확인

        반환:
        {
          "halt": bool,
          "scale_limit": float,
          "min_entry_score": int,
          "conservative_mode": bool,
        }

        profit_locks: risk_stage_config.yaml의 해당 stage profit_locks 리스트.
        외부 주입 없으면 기본값 반환.
        """
        try:
            if not profit_locks:
                return dict(_DEFAULT_LOCK_STATE)

            # threshold 내림차순 정렬 → 가장 높은 threshold부터 확인
            sorted_locks = sorted(
                profit_locks,
                key=lambda x: float(x.get("threshold", 0)),
                reverse=True,
            )

            for lock in sorted_locks:
                threshold = float(lock.get("threshold", 0))
                if daily_pnl >= threshold:
                    # halt 조건
                    if lock.get("halt", False):
                        self.is_halted = True
                        logger.info(
                            "profit_lock HALT triggered stage=%d daily_pnl=%.2f threshold=%.2f",
                            stage_id,
                            daily_pnl,
                            threshold,
                        )
                        return {
                            "halt": True,
                            "scale_limit": 0.0,
                            "min_entry_score": 999,
                            "conservative_mode": True,
                        }

                    scale = float(lock.get("scale_pct", 1.0))
                    min_sc = int(lock.get("min_entry_score", 70))
                    cons = bool(lock.get("conservative_mode", False))

                    self.current_scale_limit = scale
                    logger.info(
                        "profit_lock applied stage=%d daily_pnl=%.2f threshold=%.2f scale=%.2f",
                        stage_id,
                        daily_pnl,
                        threshold,
                        scale,
                    )
                    return {
                        "halt": False,
                        "scale_limit": scale,
                        "min_entry_score": min_sc,
                        "conservative_mode": cons,
                    }

            # 어떤 threshold도 미달 → 기본값
            return dict(_DEFAULT_LOCK_STATE)

        except Exception as exc:
            logger.error("profit_lock_manager check failed error=%s", exc)
            return dict(_DEFAULT_LOCK_STATE)

    def update_daily_pnl(self, pnl_net: float) -> None:
        """거래 결과 PnL 누적."""
        self.daily_pnl_net += pnl_net

    def reset_daily(self) -> None:
        """매일 00:00 UTC 호출. 일일 PnL 초기화."""
        self.daily_pnl_net = 0.0
        self.is_halted = False
        self.current_scale_limit = 1.0
        logger.info("profit_lock_manager daily_reset")

