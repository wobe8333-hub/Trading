from __future__ import annotations

import logging
from typing import Dict, List, Optional, Set

logger = logging.getLogger("selector.weights")

_ALL_STRATEGIES = [
    "vwap_pullback",
    "trend_continuation",
    "liquidity_sweep_reversal",
    "breakout_momentum",
    "liquidation_scalping",
    "stop_hunt_reversal",
    "ema_cross_scalping",  # [초기값]
]

_EXPECTANCY_DISABLE_THRESHOLD = 0.0   # [검증값] 기대값 < 0 → 비활성화
_WIN_RATE_HALF_THRESHOLD      = 0.40  # [검증값] 승률 40% 미만 → weight * 0.5
_WIN_RATE_LOOKBACK            = 10    # [검증값] 최근 n거래 승률 계산
_EXPECTANCY_LOOKBACK          = 20    # [검증값] 최근 n거래 기대값 계산


class StrategyWeights:
    """
    전략별 가중치 관리.

    - 초기 가중치: 모든 전략 1.0
    - update_from_performance(): 성과 기반 자동 조정
      - 최근 20거래 기대값 < 0 → disabled
      - 최근 10거래 승률 < 40% → weight * 0.5
    - re_enable(): 주간 리뷰 후 수동 재활성화
    """

    def __init__(self) -> None:
        self.weights: Dict[str, float] = {s: 1.0 for s in _ALL_STRATEGIES}
        self.disabled: Set[str] = set()
        self.disable_reason: Dict[str, str] = {}

    def update_from_performance(
        self,
        strategy: str,
        recent_pnl_net: List[float],
    ) -> None:
        """
        구현지침서 명세:
        - 최근 20거래 기대값(평균) < 0 → disabled
        - 최근 10거래 승률 < 40%      → weight * 0.5
        """
        if not recent_pnl_net:
            return

        # 기대값 계산 (최근 20거래)
        last20 = recent_pnl_net[-_EXPECTANCY_LOOKBACK:]  # [검증값]
        expectancy = sum(last20) / len(last20)

        if expectancy < _EXPECTANCY_DISABLE_THRESHOLD:  # [검증값]
            self.disabled.add(strategy)
            self.disable_reason[strategy] = f"expectancy={expectancy:.4f} < 0"
            logger.info(
                "strategy_weights disabled strategy=%s reason=%s",
                strategy,
                self.disable_reason[strategy],
            )
            return

        # 승률 계산 (최근 10거래)
        last10 = recent_pnl_net[-_WIN_RATE_LOOKBACK:]  # [검증값]
        win_rate = (
            sum(1 for p in last10 if p > 0) / len(last10) if last10 else 1.0
        )

        if win_rate < _WIN_RATE_HALF_THRESHOLD:  # [검증값]
            self.weights[strategy] = max(
                self.weights.get(strategy, 1.0) * 0.5,
                0.1,
            )
            logger.info(
                "strategy_weights halved strategy=%s win_rate=%.2f new_weight=%.2f",
                strategy,
                win_rate,
                self.weights[strategy],
            )

    def get_weight(self, strategy: str) -> float:
        """disabled이면 0.0, 아니면 현재 가중치 반환."""
        if strategy in self.disabled:
            return 0.0
        return self.weights.get(strategy, 1.0)

    def is_disabled(self, strategy: str) -> bool:
        return strategy in self.disabled

    def re_enable(self, strategy: str) -> None:
        """주간 리뷰 후 수동 재활성화."""
        self.disabled.discard(strategy)
        self.weights[strategy] = 1.0
        self.disable_reason.pop(strategy, None)
        logger.info("strategy_weights re_enabled strategy=%s", strategy)

    def get_all_weights(self) -> Dict[str, float]:
        return {s: self.get_weight(s) for s in _ALL_STRATEGIES}

