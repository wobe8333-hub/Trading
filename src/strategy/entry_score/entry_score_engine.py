from __future__ import annotations

import logging
from typing import Any, Dict

from src.strategy.entry_score.score_components import ScoreComponents
from src.strategy.entry_score.score_thresholds import score_to_scale, score_to_quality

logger = logging.getLogger("entry_score")

_SCORE_CAP = 100.0  # [검증값]


class EntryScoreEngine:
    """
    진입 품질 정량화 엔진.

    compute() 반환:
    {
      "total_score":    float,   # 0~100 (캡 적용)
      "rule_based_score": float, # Funding Bonus 제외
      "funding_bonus":  float,
      "position_scale": float,   # 0.0 / 0.4 / 0.7 / 1.0
      "entry_quality":  str,     # "A+" / "A" / "B" / "REJECT"
      "components": {
        "trend", "vwap", "regime", "scanner",
        "volume", "volatility", "orderflow", "pattern", "funding"
      }
    }

    총점 계산 (구현지침서 명세):
      raw    = trend + vwap + regime + scanner + volume + volatility + orderflow + pattern
      funding = compute_funding_bonus(funding_rate, direction)
      total  = min(raw + funding, 100)
    """

    def __init__(self) -> None:
        self._components = ScoreComponents()

    def compute(
        self,
        symbol: str,
        strategy_name: str,
        direction: str,  # "LONG" / "SHORT"
        regime: str,
        scanner_grade: str,  # "S" / "A" / "B"
        market_state: Dict[str, Any],
        orderflow_state: Dict[str, Any],
        layer_hit: Dict[str, Any],
        funding_rate: float,
    ) -> Dict[str, Any]:
        """
        모든 컴포넌트 계산 후 통합 점수 반환.
        예외 발생 시 REJECT 상태 dict 반환 — 시스템 중단 없음.
        """
        try:
            return self._compute(
                symbol,
                strategy_name,
                direction,
                regime,
                scanner_grade,
                market_state,
                orderflow_state,
                layer_hit,
                funding_rate,
            )
        except Exception as exc:
            logger.error("entry_score_engine compute failed symbol=%s error=%s", symbol, exc)
            return self._reject_result()

    def _compute(
        self,
        symbol: str,
        strategy_name: str,
        direction: str,
        regime: str,
        scanner_grade: str,
        market_state: Dict[str, Any],
        orderflow_state: Dict[str, Any],
        layer_hit: Dict[str, Any],
        funding_rate: float,
    ) -> Dict[str, Any]:
        c = self._components

        # ── 8개 컴포넌트 계산 ─────────────────────────────────
        trend = c.compute_trend_score(market_state, direction)
        vwap = c.compute_vwap_score(market_state, direction)
        regime_sc = c.compute_regime_alignment_score(strategy_name, regime)
        scanner = c.compute_scanner_bonus(scanner_grade)
        volume = c.compute_volume_score(market_state)
        volatility = c.compute_volatility_score(market_state)
        orderflow = c.compute_orderflow_score(orderflow_state)
        pattern = c.compute_pattern_quality_score(layer_hit)

        # ── 총점 계산 (구현지침서 명세) ───────────────────────
        raw = trend + vwap + regime_sc + scanner + volume + volatility + orderflow + pattern
        funding = c.compute_funding_bonus(funding_rate, direction)
        total = min(raw + funding, _SCORE_CAP)  # [검증값] 100점 캡

        # ── 포지션 비율 + 품질 등급 ───────────────────────────
        position_scale = score_to_scale(total)
        entry_quality = score_to_quality(total)

        result = {
            "total_score": round(total, 4),
            "rule_based_score": round(raw, 4),
            "funding_bonus": round(funding, 4),
            "position_scale": position_scale,
            "entry_quality": entry_quality,
            "components": {
                "trend": round(trend, 4),
                "vwap": round(vwap, 4),
                "regime": round(regime_sc, 4),
                "scanner": round(scanner, 4),
                "volume": round(volume, 4),
                "volatility": round(volatility, 4),
                "orderflow": round(orderflow, 4),
                "pattern": round(pattern, 4),
                "funding": round(funding, 4),
            },
        }

        logger.info(
            "entry_score symbol=%s strat=%s dir=%s total=%.1f quality=%s scale=%.1f",
            symbol,
            strategy_name,
            direction,
            total,
            entry_quality,
            position_scale,
        )
        return result

    @staticmethod
    def _reject_result() -> Dict[str, Any]:
        return {
            "total_score": 0.0,
            "rule_based_score": 0.0,
            "funding_bonus": 0.0,
            "position_scale": 0.0,
            "entry_quality": "REJECT",
            "components": {
                "trend": 0.0,
                "vwap": 0.0,
                "regime": 0.0,
                "scanner": 0.0,
                "volume": 0.0,
                "volatility": 0.0,
                "orderflow": 0.0,
                "pattern": 0.0,
                "funding": 0.0,
            },
        }

