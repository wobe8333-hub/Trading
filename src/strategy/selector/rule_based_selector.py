from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from src.strategy.selector.ml_selector import MLStrategySelector
from src.strategy.selector.strategy_weights import (
    StrategyWeights,
    _ALL_STRATEGIES,
)
from src.utils.config_loader import load_strategy_config

logger = logging.getLogger("selector.rule_based")

_COLD_START_TRADES = 50  # [검증값]
_COLD_START_STRATEGIES = [
    "vwap_pullback",
    "trend_continuation",
    "liquidity_sweep_reversal",
    "stop_hunt_reversal",
    "ema_cross_scalping",  # [초기값]
]  # [초기값] RANGE 국면 허용 전략 포함


class RuleBasedSelector:
    """
    Regime 허용 + 코인 유형 매칭 + 성과 기반 우선순위로 전략 선택.

    select() 반환: 허용된 전략 이름 리스트 (우선순위 순서, 내림차순)

    필터링 순서 (구현지침서 명세):
    1. strategy_weights.is_disabled() 제외
    2. strategy.is_allowed(macro_state, regime) 통과
    3. coin_type이 preferred_coin_types에 포함되면 가중치 보너스
    4. strategy_weights.get_weight() 기반 가중치 정렬
    5. 가중치 내림차순 반환
    """

    def __init__(
        self,
        weights: Optional[StrategyWeights] = None,
        ml_selector: Optional[MLStrategySelector] = None,
    ) -> None:
        self._weights = weights or StrategyWeights()
        self._ml = ml_selector or MLStrategySelector()
        self._strategy_cfg = load_strategy_config()

        # 전략 인스턴스 캐시 (is_allowed 호출용)
        from src.strategy.strategy_library.vwap_pullback import VWAPPullback
        from src.strategy.strategy_library.trend_continuation import (
            TrendContinuation,
        )
        from src.strategy.strategy_library.liquidity_sweep_reversal import (
            LiquiditySweepReversal,
        )
        from src.strategy.strategy_library.breakout_momentum import BreakoutMomentum
        from src.strategy.strategy_library.liquidation_scalping import (
            LiquidationScalping,
        )
        from src.strategy.strategy_library.stop_hunt_reversal import (
            StopHuntReversal,
        )
        from src.strategy.strategy_library.ema_cross_scalping import (
            EMACrossScalping,
        )

        self._strategies: Dict[str, Any] = {
            "vwap_pullback": VWAPPullback(self._strategy_cfg["vwap_pullback"]),
            "trend_continuation": TrendContinuation(
                self._strategy_cfg["trend_continuation"]
            ),
            "liquidity_sweep_reversal": LiquiditySweepReversal(
                self._strategy_cfg["liquidity_sweep_reversal"]
            ),
            "breakout_momentum": BreakoutMomentum(
                self._strategy_cfg["breakout_momentum"]
            ),
            "liquidation_scalping": LiquidationScalping(
                self._strategy_cfg["liquidation_scalping"]
            ),
            "stop_hunt_reversal": StopHuntReversal(
                self._strategy_cfg["stop_hunt_reversal"]
            ),
            "ema_cross_scalping": EMACrossScalping(
                self._strategy_cfg["ema_cross_scalping"]
            ),
        }

    def select(
        self,
        symbol: str,
        macro_state: str,
        regime: str,
        coin_type: str,
        entry_score_min: int,
        trade_count: int,
    ) -> List[str]:
        """
        허용된 전략 이름 리스트 반환 (우선순위 순서).
        예외 발생 시 Cold Start 전략 반환 — 시스템 중단 없음.
        """
        try:
            return self._select(
                symbol,
                macro_state,
                regime,
                coin_type,
                entry_score_min,
                trade_count,
            )
        except Exception as exc:
            logger.error("rule_based_selector select failed symbol=%s error=%s", symbol, exc)
            return list(_COLD_START_STRATEGIES)

    def _select(
        self,
        symbol: str,
        macro_state: str,
        regime: str,
        coin_type: str,
        entry_score_min: int,
        trade_count: int,
    ) -> List[str]:
        # ── RISK_OFF 전면 차단 (명세) ─────────────────────────────
        if macro_state == "RISK_OFF":
            return []

        # ── Cold Start 처리 ───────────────────────────────────
        if trade_count < _COLD_START_TRADES:  # [검증값]
            logger.info(
                "rule_based_selector cold_start trade_count=%d returning %s",
                trade_count,
                _COLD_START_STRATEGIES,
            )
            return list(_COLD_START_STRATEGIES)

        scored: List[Dict[str, Any]] = []

        for name in _ALL_STRATEGIES:
            strat = self._strategies.get(name)
            if strat is None:
                continue

            # ── 필터 1: disabled 제외 ─────────────────────────
            if self._weights.is_disabled(name):
                logger.debug("selector skip disabled strategy=%s", name)
                continue

            # ── 필터 2: is_allowed 통과 여부 ──────────────────
            if not strat.is_allowed(macro_state, regime):
                logger.debug(
                    "selector skip not_allowed strategy=%s macro=%s regime=%s",
                    name,
                    macro_state,
                    regime,
                )
                continue

            # ── 필터 3 + 4: coin_type 보너스 + 가중치 ─────────
            base_weight = self._weights.get_weight(name)
            pref_types = self._strategy_cfg[name].get("preferred_coin_types", [])
            coin_bonus = 0.2 if coin_type in pref_types else 0.0  # [초기값]
            final_weight = base_weight + coin_bonus

            scored.append({"name": name, "weight": final_weight})

        # ── 필터 5: 가중치 내림차순 정렬 ──────────────────────
        scored.sort(key=lambda x: x["weight"], reverse=True)

        # ── ML 인터페이스 (현재 pass-through) ─────────────────
        if self._ml.is_active():
            score_dict = {s["name"]: s["weight"] for s in scored}
            adjusted = self._ml.adjust_weights(score_dict)
            scored = sorted(
                [{"name": k, "weight": v} for k, v in adjusted.items()],
                key=lambda x: x["weight"],
                reverse=True,
            )

        result = [s["name"] for s in scored]
        logger.info(
            "rule_based_selector symbol=%s macro=%s regime=%s coin=%s result=%s",
            symbol, macro_state, regime, coin_type, result,
        )
        for _s in scored:
            logger.debug(
                "rule_based_selector weight strategy=%s weight=%.3f",
                _s["name"], _s["weight"],
            )
        return result

