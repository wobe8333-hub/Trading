from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from src.utils.config_loader import ConfigManager

logger = logging.getLogger("growth.stage_manager")

_DEFAULT_STAGE = {
    "id": 1,
    "equity_min": 700,
    "equity_max": 1500,
    "risk_pct_per_trade": 0.032,  # [초기값]
    "daily_loss_limit": -35,
    "profit_locks": [],
}


class StageManager:
    """
    risk_stage_config.yaml 기반 Stage 관리.

    get_current_stage(): equity_min <= equity < equity_max 인 stage 반환
    check_stage_transition(): 이전/현재 equity 비교 → Stage 변화 감지
    """

    def __init__(self) -> None:
        cfg = ConfigManager().load_stage_config()
        self._stages: List[Dict[str, Any]] = cfg if isinstance(cfg, list) else []

    def get_current_stage(self, equity: float) -> Dict[str, Any]:
        """equity에 맞는 Stage dict 반환. 없으면 마지막 Stage."""
        try:
            for stage in self._stages:
                e_min = float(stage.get("equity_min", 0))
                e_max = float(stage.get("equity_max", float("inf")))
                if e_min <= equity < e_max:
                    return dict(stage)
            # equity가 최고 단계를 초과하면 마지막 Stage 반환
            if self._stages:
                return dict(self._stages[-1])
            return dict(_DEFAULT_STAGE)
        except Exception as exc:
            logger.error("stage_manager get_current_stage failed error=%s", exc)
            return dict(_DEFAULT_STAGE)

    def get_risk_pct(self, equity: float) -> float:
        """현재 Stage의 risk_pct_per_trade 반환."""
        stage = self.get_current_stage(equity)
        return float(stage.get("risk_pct_per_trade", 0.032))  # [초기값]

    def check_stage_transition(
        self,
        prev_equity: float,
        curr_equity: float,
    ) -> Dict[str, Any]:
        """
        Stage 변화 감지.
        반환: {"transitioned": bool, "from": int, "to": int}
        """
        try:
            prev_stage = self.get_current_stage(prev_equity)
            curr_stage = self.get_current_stage(curr_equity)

            prev_id = int(prev_stage.get("id", 1))
            curr_id = int(curr_stage.get("id", 1))
            transitioned = prev_id != curr_id

            if transitioned:
                logger.info(
                    "stage_manager stage_transition from=%d to=%d equity=%.2f",
                    prev_id,
                    curr_id,
                    curr_equity,
                )

            return {
                "transitioned": transitioned,
                "from": prev_id,
                "to": curr_id,
            }
        except Exception as exc:
            logger.error(
                "stage_manager check_stage_transition failed error=%s", exc
            )
            return {"transitioned": False, "from": 1, "to": 1}

