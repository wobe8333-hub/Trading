from __future__ import annotations

import logging

logger = logging.getLogger("risk.recovery_engine")


class RecoveryEngine:
    """
    드로다운 복구 단계별 리스크 조정.

    복구 진행률 기준 리스크 배율:
    0%~50%:  base * 0.5
    50%~75%: base * 0.75
    75%~100%: base * 0.90
    100%+:   base (정상)
    """

    def get_recovery_risk_pct(
        self,
        drawdown_state: str,
        base_risk_pct: float,
        recovery_progress: float,  # 0.0~1.0
    ) -> float:
        """
        구현지침서 명세:
        if recovery_progress < 0.50:  return base * 0.5
        elif recovery_progress < 0.75: return base * 0.75
        elif recovery_progress < 1.00: return base * 0.90
        else: return base
        """
        try:
            if recovery_progress < 0.50:  # [초기값]
                return round(base_risk_pct * 0.50, 6)
            elif recovery_progress < 0.75:  # [초기값]
                return round(base_risk_pct * 0.75, 6)
            elif recovery_progress < 1.00:  # [초기값]
                return round(base_risk_pct * 0.90, 6)
            return base_risk_pct
        except Exception as exc:
            logger.error("recovery_engine get_recovery_risk_pct failed error=%s", exc)
            return base_risk_pct

    @staticmethod
    def compute_recovery_progress(
        current_equity: float,
        peak_equity: float,
        trough_equity: float,
    ) -> float:
        """
        구현지침서 명세:
        if peak == trough: return 1.0
        return (current - trough) / (peak - trough)
        """
        if abs(peak_equity - trough_equity) < 1e-9:
            return 1.0
        progress = (current_equity - trough_equity) / (
            peak_equity - trough_equity
        )
        return max(0.0, min(1.0, progress))

