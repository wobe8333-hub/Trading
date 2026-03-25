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
        self._load_from_disk()

    def _load_from_disk(self) -> None:
        import glob
        try:
            files = sorted(glob.glob(os.path.join(_TRADE_DIR, "*.jsonl")))
            for fpath in files:
                with open(fpath, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                self._trades.append(json.loads(line))
                            except Exception:
                                pass
            logger.info("analytics_engine loaded %d trades from disk", len(self._trades))
        except Exception as exc:
            logger.error("analytics_engine load_from_disk failed error=%s", exc)

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

    def update_trade_pnl(
        self,
        trade_id: str,
        pnl_net: float,
        r_multiple: float,
    ) -> None:
        """
        청산 시 trade_id 기준으로 pnl_net / r_multiple 업데이트.
        in-memory + JSONL 파일 overwrite 방식. [FIX 12]
        """
        try:
            import glob
            # 1. in-memory 업데이트
            for trade in self._trades:
                if trade.get("trade_id") == trade_id:
                    trade["pnl_net"] = pnl_net
                    trade["r_multiple"] = r_multiple
                    break

            # 2. JSONL 파일 overwrite (trade_id 기준)
            files = sorted(glob.glob(os.path.join(_TRADE_DIR, "*.jsonl")))
            for fpath in files:
                lines: List[str] = []
                found = False
                try:
                    with open(fpath, "r", encoding="utf-8") as f:
                        for line in f:
                            line = line.strip()
                            if not line:
                                continue
                            try:
                                record = json.loads(line)
                                if record.get("trade_id") == trade_id:
                                    record["pnl_net"] = pnl_net
                                    record["r_multiple"] = r_multiple
                                    found = True
                                lines.append(
                                    json.dumps(record, ensure_ascii=False)
                                )
                            except Exception:
                                lines.append(line)
                    if found:
                        with open(fpath, "w", encoding="utf-8") as f:
                            f.write("\n".join(lines) + "\n")
                        logger.info(
                            "analytics_engine update_trade_pnl "
                            "trade_id=%s pnl=%.4f r=%.4f",
                            trade_id, pnl_net, r_multiple,
                        )
                        _all = self._trades
                        _n = len(_all)
                        if _n > 0:
                            _wins = [t for t in _all if t.get("pnl_net", 0) > 0]
                            _losses = [t for t in _all if t.get("pnl_net", 0) <= 0]
                            _wr = len(_wins) / _n
                            _tpnl = sum(t.get("pnl_net", 0) for t in _all)
                            _aw = sum(t["pnl_net"] for t in _wins) / max(len(_wins), 1)
                            _al = sum(t["pnl_net"] for t in _losses) / max(len(_losses), 1)
                            _pf = abs(_aw * len(_wins)) / abs(_al * len(_losses)) if _losses else 0.0
                            _exp = (_wr * _aw) + ((1 - _wr) * _al)
                            logger.info(
                                "analytics_summary trades=%d wins=%d losses=%d "
                                "win_rate=%.3f total_pnl=%.4f "
                                "avg_win=%.4f avg_loss=%.4f "
                                "profit_factor=%.3f expectancy=%.4f",
                                _n, len(_wins), len(_losses),
                                _wr, _tpnl, _aw, _al, _pf, _exp,
                            )
                        return
                except Exception as exc:
                    logger.error(
                        "analytics_engine update_trade_pnl "
                        "file_error fpath=%s error=%s",
                        fpath, exc,
                    )
        except Exception as exc:
            logger.error(
                "analytics_engine update_trade_pnl failed "
                "trade_id=%s error=%s",
                trade_id, exc,
            )

