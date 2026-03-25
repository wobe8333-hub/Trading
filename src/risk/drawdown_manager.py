from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List

from src.utils.config_loader import ConfigManager

logger = logging.getLogger("risk.drawdown_manager")


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class DrawdownManager:
    """
    드로다운 상태 감지 및 단계별 리스크 조정.

    상태 전환 (system_config.yaml 임계값):
    NORMAL  → dd < 0.15
    ALERT   → 0.15 <= dd < 0.25
    DANGER  → 0.25 <= dd < 0.35
    HALT    → dd >= 0.35
    """

    def __init__(self) -> None:
        cfg = ConfigManager().load_system_config()
        self._alert_pct = float(cfg.get("drawdown_alert_pct", 0.15))
        self._danger_pct = float(cfg.get("drawdown_danger_pct", 0.25))
        self._halt_pct = float(cfg.get("drawdown_halt_pct", 0.35))

        self.peak_equity: float = 0.0
        self.current_equity: float = 0.0
        self.drawdown_state: str = "NORMAL"
        self.state_entry_time: datetime = _utcnow()

    def update_equity(self, equity: float) -> None:
        """equity 갱신 → peak 업데이트 → 상태 전환."""
        self.current_equity = equity
        if equity > self.peak_equity:
            self.peak_equity = equity

        logger.debug(
            "drawdown update equity=%.2f peak=%.2f dd_pct=%.4f state=%s",
            self.current_equity, self.peak_equity,
            self.get_drawdown_pct(), self.drawdown_state,
        )
        new_state = self._compute_state()
        if new_state != self.drawdown_state:
            logger.info(
                "drawdown_manager state_change %s→%s "
                "equity=%.2f peak=%.2f dd_pct=%.4f",
                self.drawdown_state, new_state,
                self.current_equity, self.peak_equity,
                self.get_drawdown_pct(),
            )
            self.drawdown_state = new_state
            self.state_entry_time = _utcnow()

    def get_drawdown_pct(self) -> float:
        """현재 드로다운 비율."""
        if self.peak_equity <= 0:
            return 0.0
        return (self.peak_equity - self.current_equity) / self.peak_equity

    def get_state(self) -> str:
        return self.drawdown_state

    def get_risk_adjustment(self) -> Dict[str, Any]:
        """
        구현지침서 명세:
        NORMAL: risk_multiplier=1.0, max_strategies=6, min_entry_score=70
        ALERT:  risk_multiplier=0.5, max_strategies=2, min_entry_score=75
        DANGER: risk_multiplier=0.25,max_strategies=1, min_entry_score=80
        HALT:   risk_multiplier=0.0, max_strategies=0, min_entry_score=999
        """
        table = {
            "NORMAL": {
                "risk_multiplier": 1.0,
                "max_strategies": 6,
                "min_entry_score": 70,
            },
            "ALERT": {
                "risk_multiplier": 0.5,
                "max_strategies": 2,
                "min_entry_score": 75,
            },
            "DANGER": {
                "risk_multiplier": 0.25,
                "max_strategies": 1,
                "min_entry_score": 80,
            },
            "HALT": {
                "risk_multiplier": 0.0,
                "max_strategies": 0,
                "min_entry_score": 999,
            },
        }
        return dict(table.get(self.drawdown_state, table["NORMAL"]))

    def check_halt_conditions(self, daily_pnl_history: List[float]) -> bool:
        """최근 3일 연속 손실 여부 확인."""
        if len(daily_pnl_history) < 3:
            return False
        return all(p < 0 for p in daily_pnl_history[-3:])

    def _compute_state(self) -> str:
        dd = self.get_drawdown_pct()
        if dd >= self._halt_pct:
            return "HALT"
        if dd >= self._danger_pct:
            return "DANGER"
        if dd >= self._alert_pct:
            return "ALERT"
        return "NORMAL"

