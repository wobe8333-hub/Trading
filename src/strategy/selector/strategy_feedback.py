from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any, Dict, List

from src.strategy.selector.strategy_weights import StrategyWeights

logger = logging.getLogger("selector.feedback")

_MAX_HISTORY = 500  # [초기값] 전략별 최대 거래 기록 보관 수


class StrategyFeedback:
    """
    전략별 거래 결과 기록 및 성과 분석.

    record() → get_recent_expectancy() / get_recent_win_rate() → trigger_weight_update()
    """

    def __init__(self, weights: StrategyWeights) -> None:
        self._weights = weights
        self._history: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    def record(
        self,
        strategy: str,
        symbol: str,
        regime: str,
        pnl_net: float,
        r_multiple: float,
    ) -> None:
        """거래 결과를 전략별 히스토리에 추가."""
        entry = {
            "strategy": strategy,
            "symbol": symbol,
            "regime": regime,
            "pnl_net": pnl_net,
            "r_multiple": r_multiple,
        }
        self._history[strategy].append(entry)

        if len(self._history[strategy]) > _MAX_HISTORY:
            self._history[strategy] = self._history[strategy][-_MAX_HISTORY:]

        _hist = self._history[strategy]
        _n_hist = len(_hist)
        _exp = sum(h["pnl_net"] for h in _hist[-20:]) / min(_n_hist, 20) if _n_hist > 0 else 0.0
        _wr = sum(1 for h in _hist[-10:] if h["pnl_net"] > 0) / min(_n_hist, 10) if _n_hist > 0 else 0.0
        logger.info(
            "strategy_feedback strategy=%s pnl=%.4f r=%.2f "
            "total_trades=%d expectancy_20=%.4f win_rate_10=%.3f",
            strategy, pnl_net, r_multiple,
            _n_hist, _exp, _wr,
        )

    def get_recent_expectancy(self, strategy: str, n: int = 20) -> float:
        """최근 n거래 pnl_net 평균 반환. 기록 없으면 0.0."""
        hist = self._history.get(strategy, [])
        if not hist:
            return 0.0
        last_n = hist[-n:]
        return sum(h["pnl_net"] for h in last_n) / len(last_n)

    def get_recent_win_rate(self, strategy: str, n: int = 10) -> float:
        """최근 n거래 승률 반환. 기록 없으면 1.0."""
        hist = self._history.get(strategy, [])
        if not hist:
            return 1.0
        last_n = hist[-n:]
        wins = sum(1 for h in last_n if h["pnl_net"] > 0)
        return wins / len(last_n)

    def trigger_weight_update(self) -> None:
        """모든 전략의 가중치를 최신 성과 기반으로 업데이트."""
        from src.strategy.selector.strategy_weights import _ALL_STRATEGIES

        for strategy in _ALL_STRATEGIES:
            hist = self._history.get(strategy, [])
            if not hist:
                continue
            pnl_list = [h["pnl_net"] for h in hist]
            self._weights.update_from_performance(strategy, pnl_list)
            logger.info(
                "strategy_feedback weight_update strategy=%s expectancy=%.4f win_rate=%.2f",
                strategy,
                self.get_recent_expectancy(strategy),
                self.get_recent_win_rate(strategy),
            )

    def get_history(self, strategy: str) -> List[Dict[str, Any]]:
        return list(self._history.get(strategy, []))

