from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("analytics.engine")

_COLD_START_TRADES = 50  # [검증값]
_TRADE_DIR = "data/trade_history"


class AnalyticsEngine:
    """
    거래 결과 24개 항목 기록 및 조회.
    저장 경로: data/trade_history/YYYY-MM-DD.jsonl
    """

    def __init__(self) -> None:
        self._trades: List[Dict[str, Any]] = []
        os.makedirs(_TRADE_DIR, exist_ok=True)

    def record_trade(self, trade: Dict[str, Any]) -> None:
        """24개 항목 거래 기록 저장."""
        try:
            if "timestamp" not in trade or not trade["timestamp"]:
                trade["timestamp"] = datetime.now(timezone.utc).isoformat()
            self._trades.append(trade)
            self._persist(trade)
        except Exception as exc:
            logger.error("analytics_engine record_trade failed error=%s", exc)

    def _persist(self, trade: Dict[str, Any]) -> None:
        try:
            date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            path = os.path.join(_TRADE_DIR, f"{date_str}.jsonl")
            with open(path, "a", encoding="utf-8") as f:
                f.write(json.dumps(trade, ensure_ascii=False) + "\n")
        except Exception as exc:
            logger.error("analytics_engine persist failed error=%s", exc)

    def get_trades(
        self,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        strategy: Optional[str] = None,
        symbol: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        result = list(self._trades)
        if strategy:
            result = [t for t in result if t.get("strategy") == strategy]
        if symbol:
            result = [t for t in result if t.get("symbol") == symbol]
        return result

    def get_total_trade_count(self) -> int:
        return len(self._trades)

    def get_cold_start_flag(self) -> bool:
        return self.get_total_trade_count() < _COLD_START_TRADES

