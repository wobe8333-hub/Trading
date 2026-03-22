from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger("analytics.layer_analyzer")


class LayerAnalyzer:
    """전략 레이어별 충족률 + 기대값 분석."""

    def analyze(self, trades: List[Dict[str, Any]]) -> Dict[str, Any]:
        try:
            return self._analyze(trades)
        except Exception as exc:
            logger.error("layer_analyzer analyze failed error=%s", exc)
            return {
                "layer1_pass_rate": 0.0,
                "layer2_pass_rate": 0.0,
                "layer3_pass_rate": 0.0,
                "expectancy_by_layer_combo": {"1_2_3": 0.0, "1_2": 0.0},
            }

    def _analyze(self, trades: List[Dict[str, Any]]) -> Dict[str, Any]:
        if not trades:
            return {
                "layer1_pass_rate": 0.0,
                "layer2_pass_rate": 0.0,
                "layer3_pass_rate": 0.0,
                "expectancy_by_layer_combo": {"1_2_3": 0.0, "1_2": 0.0},
            }

        n = len(trades)
        l1_pass = l2_pass = l3_pass = 0
        combo_123: List[float] = []
        combo_12: List[float] = []

        for t in trades:
            lh = t.get("strategy_layer_hit", {})
            l1 = bool(lh.get("layer1"))
            l2 = bool(lh.get("layer2"))
            l3 = bool(lh.get("layer3"))
            pnl = float(t.get("pnl_net", 0.0))

            if l1:
                l1_pass += 1
            if l2:
                l2_pass += 1
            if l3:
                l3_pass += 1

            if l1 and l2 and l3:
                combo_123.append(pnl)
            elif l1 and l2:
                combo_12.append(pnl)

        return {
            "layer1_pass_rate": round(l1_pass / n, 4),
            "layer2_pass_rate": round(l2_pass / n, 4),
            "layer3_pass_rate": round(l3_pass / n, 4),
            "expectancy_by_layer_combo": {
                "1_2_3": round(sum(combo_123) / len(combo_123), 4) if combo_123 else 0.0,
                "1_2": round(sum(combo_12) / len(combo_12), 4) if combo_12 else 0.0,
            },
        }

