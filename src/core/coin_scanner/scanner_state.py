from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger("scanner.state")


class ScannerState:
    """
    스캐너 결과 싱글톤 저장소.
    메인 루프와 분석 엔진이 공유한다.
    """

    _instance: Optional["ScannerState"] = None

    def __new__(cls) -> "ScannerState":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_state()
        return cls._instance

    def _init_state(self) -> None:
        self._top3: List[Dict[str, Any]] = []
        self._full_ranking: List[Dict[str, Any]] = []
        self._coin_types: Dict[str, str] = {}
        self._last_scan_time: float = 0.0
        self._macro_state_at_scan: str = "NEUTRAL"
        self._scan_count: int = 0

    # ── 쓰기 ──────────────────────────────────────────────────

    def update(
        self,
        top3: List[Dict[str, Any]],
        full_ranking: List[Dict[str, Any]],
        coin_types: Dict[str, str],
        macro_state: str,
    ) -> None:
        self._top3 = list(top3)
        self._full_ranking = list(full_ranking)
        self._coin_types = dict(coin_types)
        self._last_scan_time = time.time()
        self._macro_state_at_scan = macro_state
        self._scan_count += 1
        logger.info(
            "scanner_state updated scan_count=%d top3=%s macro=%s",
            self._scan_count,
            [r["symbol"] for r in top3],
            macro_state,
        )

    # ── 읽기 ──────────────────────────────────────────────────

    def get_top3(self) -> List[Dict[str, Any]]:
        return list(self._top3)

    def get_full_ranking(self) -> List[Dict[str, Any]]:
        return list(self._full_ranking)

    def get_symbol_score(self, symbol: str) -> float:
        for item in self._full_ranking:
            if item.get("symbol") == symbol:
                return float(item.get("score", 0.0))
        return 0.0

    def is_in_top3(self, symbol: str) -> bool:
        return any(r.get("symbol") == symbol for r in self._top3)

    def get_coin_type(self, symbol: str) -> str:
        return self._coin_types.get(symbol, "UNKNOWN")

    def get_snapshot(self) -> Dict[str, Any]:
        return {
            "top3":               self.get_top3(),
            "full_ranking":       self.get_full_ranking(),
            "last_scan_time":     self._last_scan_time,
            "macro_state_at_scan": self._macro_state_at_scan,
            "scan_count":         self._scan_count,
        }

    @classmethod
    def reset(cls) -> None:
        """테스트 격리용 싱글톤 초기화."""
        if cls._instance is not None:
            cls._instance._init_state()
