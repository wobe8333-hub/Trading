from __future__ import annotations

import logging
from typing import Any, Dict, List

logger = logging.getLogger("analytics.expectancy")


def _compute_expectancy_from_trades(trades: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not trades:
        return {
            "expectancy": 0.0,
            "win_rate": 0.0,
            "avg_win": 0.0,
            "avg_loss": 0.0,
            "total_trades": 0,
            "profit_factor": 0.0,
            "avg_rr": 0.0,
        }

    wins = [t["pnl_net"] for t in trades if t.get("pnl_net", 0) > 0]
    losses = [t["pnl_net"] for t in trades if t.get("pnl_net", 0) <= 0]

    win_rate = len(wins) / len(trades)
    avg_win = sum(wins) / len(wins) if wins else 0.0
    avg_loss = abs(sum(losses) / len(losses)) if losses else 0.0
    expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)

    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0.0

    rrs = [t.get("r_multiple", 0.0) for t in trades]
    avg_rr = sum(rrs) / len(rrs) if rrs else 0.0

    return {
        "expectancy": round(expectancy, 4),
        "win_rate": round(win_rate, 4),
        "avg_win": round(avg_win, 4),
        "avg_loss": round(avg_loss, 4),
        "total_trades": len(trades),
        "profit_factor": round(profit_factor, 4),
        "avg_rr": round(avg_rr, 4),
    }


class ExpectancyEngine:
    """거래 리스트 기반 기대값 / 승률 / 수익 팩터 계산."""

    def compute_expectancy(self, trades: List[Dict[str, Any]]) -> Dict[str, Any]:
        try:
            return _compute_expectancy_from_trades(trades)
        except Exception as exc:
            logger.error("expectancy_engine failed error=%s", exc)
            return _compute_expectancy_from_trades([])

    def compute_by_strategy(self, trades: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        return self._group_by(trades, "strategy")

    def compute_by_regime(self, trades: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        return self._group_by(trades, "regime")

    def compute_by_symbol(self, trades: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        return self._group_by(trades, "symbol")

    def compute_by_session(self, trades: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        return self._group_by(trades, "session")

    def compute_by_coin_type(self, trades: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        return self._group_by(trades, "coin_type")

    def _group_by(self, trades: List[Dict[str, Any]], key: str) -> Dict[str, Dict[str, Any]]:
        groups: Dict[str, List[Dict[str, Any]]] = {}
        for t in trades:
            k = str(t.get(key, "unknown"))
            groups.setdefault(k, []).append(t)
        return {k: _compute_expectancy_from_trades(v) for k, v in groups.items()}

