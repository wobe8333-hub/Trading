from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, Optional

logger = logging.getLogger("app.state_store")

_CACHE_DIR = "data/analytics_cache"
_STATE_FILE = os.path.join(_CACHE_DIR, "state.json")

_DEFAULT_STATE: Dict[str, Any] = {
    "equity": 700.0,
    "daily_pnl": 0.0,
    "daily_trade_count": 0,
    "total_trade_count": 0,
    "macro_state": "NEUTRAL",
    "top3": [],
    "open_positions": {},
    "drawdown_state": "NORMAL",
    "kill_switch_active": False,
    "last_scan_time": 0.0,
    "session_start_equity": 700.0,
}


class StateStore:
    """
    시스템 전역 상태 싱글톤 저장소.
    update() / get() / reset_daily() / save_to_disk() / load_from_disk()
    """

    _instance: Optional["StateStore"] = None

    def __new__(cls) -> "StateStore":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._state = dict(_DEFAULT_STATE)
            os.makedirs(_CACHE_DIR, exist_ok=True)
        return cls._instance

    def update(self, key: str, value: Any) -> None:
        self._state[key] = value

    def get(self, key: str, default: Any = None) -> Any:
        return self._state.get(key, default)

    def get_all(self) -> Dict[str, Any]:
        return dict(self._state)

    def reset_daily(self) -> None:
        """매일 00:00 UTC 호출."""
        self._state["daily_pnl"] = 0.0
        self._state["daily_trade_count"] = 0
        logger.info("state_store daily_reset")

    def save_to_disk(self) -> None:
        try:
            with open(_STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(self._state, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            logger.error("state_store save_to_disk failed error=%s", exc)

    def load_from_disk(self) -> None:
        try:
            if os.path.exists(_STATE_FILE):
                with open(_STATE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self._state.update(data)
                logger.info("state_store loaded from disk")
        except Exception as exc:
            logger.error("state_store load_from_disk failed error=%s", exc)

    @classmethod
    def reset_singleton(cls) -> None:
        """테스트용 싱글톤 초기화."""
        cls._instance = None

