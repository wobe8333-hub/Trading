from __future__ import annotations

import logging
from typing import Any, Dict

logger = logging.getLogger("selector.ml")

_ML_ACTIVATION_THRESHOLD = 500  # [검증값] 활성화 조건: 500거래 이상
_ML_WIN_RATE_THRESHOLD = 0.55  # [검증값] 활성화 조건: 승률 55% 이상


class MLStrategySelector:
    """
    ML 전략 선택기 — 현재 비활성 상태 (인터페이스 예약).

    구현지침서 명세:
    - is_active() → 항상 False (500거래 + 승률 55%+ + ML 담당자 확보 시 활성화)
    - adjust_weights() → 그대로 통과 (현재)
    - get_status() → 현재 상태 dict 반환
    """

    def __init__(self, trade_count: int = 0) -> None:
        self._trade_count = trade_count

    def is_active(self) -> bool:
        """현재 항상 False. ML 활성화 조건 미충족."""
        return False

    def adjust_weights(self, rule_based_scores: Dict[str, Any]) -> Dict[str, Any]:
        """현재 rule_based_scores를 그대로 통과."""
        return rule_based_scores

    def get_status(self) -> Dict[str, Any]:
        return {
            "active": False,
            "activation_condition": (
                f"{_ML_ACTIVATION_THRESHOLD}거래 + 승률 "
                f"{_ML_WIN_RATE_THRESHOLD*100:.0f}%+ + ML 담당자 확보"
            ),
            "current_trade_count": self._trade_count,
        }

    def update_trade_count(self, count: int) -> None:
        self._trade_count = count

