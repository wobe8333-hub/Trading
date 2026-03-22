from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional

from websocket import WebSocketApp


logger = logging.getLogger("market_data")


class BybitWsClient:
    """
    Bybit WebSocket thin wrapper.
    재연결: 최대 3회 / 1초 간격. [검증값]
    3회 실패 시 kill_switch_signal = True.
    stale_timeout: ws_refresh_max_ms 기준. [검증값: 100ms]
    """

    def __init__(
        self,
        url: str,
        symbols: List[str],
        on_message: Callable[[str, str, Dict[str, Any]], None],
        logger: logging.Logger = logger,
        max_retries: int = 3,           # [검증값]
        backoff_seconds: float = 1.0,   # [검증값]
        stale_timeout_ms: int = 100,    # [검증값] ws_refresh_max_ms
    ) -> None:
        self._url = url
        self._symbols = symbols
        self._on_message_cb = on_message
        self._logger = logger
        self._max_retries = max_retries
        self._backoff_seconds = backoff_seconds
        self._stale_timeout_ms = stale_timeout_ms

        self._ws: Optional[WebSocketApp] = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._connected = False
        self._last_msg_ts: float = 0.0
        self._last_symbol_ts: Dict[str, float] = {}

        self.kill_switch_signal: bool = False

        # 콜백 딕셔너리 {topic_prefix: callback_fn}
        self._callbacks: Dict[str, Callable] = {}

    # ──────────────────────────────────────────────────────────
    # Public subscribe API
    # ──────────────────────────────────────────────────────────

    def subscribe_ticker(self, symbols: List[str], callback: Callable) -> None:
        """ticker 구독 등록. 콜백 형식: callback(message: dict)"""
        for s in symbols:
            self._callbacks[f"tickers.{s}"] = callback

    def subscribe_orderbook(
        self, symbols: List[str], depth: int = 50, callback: Callable = None
    ) -> None:
        """orderbook 구독 등록."""
        for s in symbols:
            self._callbacks[f"orderbook.{depth}.{s}"] = callback

    def subscribe_trades(self, symbols: List[str], callback: Callable) -> None:
        """trade 구독 등록."""
        for s in symbols:
            self._callbacks[f"publicTrade.{s}"] = callback

    def check_freshness(self, symbol: str) -> bool:
        """
        해당 심볼의 마지막 WS 수신이 stale_timeout_ms 이내인지 확인.
        False 이면 REST fallback 필요.
        """
        last_ts = self._last_symbol_ts.get(symbol, 0.0)
        elapsed_ms = (time.time() - last_ts) * 1000
        return elapsed_ms <= self._stale_timeout_ms

    # ──────────────────────────────────────────────────────────
    # Connection management
    # ──────────────────────────────────────────────────────────

    def connect(self) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_forever, daemon=True)
        self._thread.start()

    def close(self) -> None:
        self._stop_event.set()
        if self._ws:
            self._ws.close()

    def reconnect(self) -> None:
        """재연결 시도. 최대 3회 / 1초 간격. 실패 시 kill_switch_signal = True."""
        self._logger.info("market_data ws reconnect start")
        self.close()
        for attempt in range(self._max_retries):
            time.sleep(self._backoff_seconds)
            try:
                self.connect()
                time.sleep(0.5)
                if self._connected:
                    self._logger.info("market_data ws reconnect success attempt=%d", attempt + 1)
                    return
            except Exception as exc:
                self._logger.error("market_data ws reconnect attempt=%d error=%s", attempt + 1, exc)
        self.kill_switch_signal = True
        self._logger.error("market_data ws reconnect failed 3 times, kill_switch_signal=True")

    def _on_disconnect(self, ws) -> None:
        """WS 연결 끊김 시 자동 재연결 트리거."""
        self._connected = False
        self._logger.error("market_data ws disconnect event — triggering reconnect")
        if not self._stop_event.is_set():
            threading.Thread(target=self.reconnect, daemon=True).start()

    def _run_forever(self) -> None:
        retries = 0
        while not self._stop_event.is_set() and retries <= self._max_retries:
            self._ws = WebSocketApp(
                self._url,
                on_open=self._on_open,
                on_message=self._handle_message,
                on_close=self._on_close,
                on_error=self._on_error,
            )
            self._ws.run_forever()
            retries += 1
            if not self._stop_event.is_set():
                self._logger.info(
                    "market_data ws disconnected retry=%d/%d", retries, self._max_retries
                )
                time.sleep(self._backoff_seconds)
        if retries > self._max_retries:
            self.kill_switch_signal = True
            self._logger.error("market_data ws max_retries exceeded, kill_switch_signal=True")

    # ──────────────────────────────────────────────────────────
    # WS event handlers
    # ──────────────────────────────────────────────────────────

    def _on_open(self, _) -> None:
        self._connected = True
        self._last_msg_ts = time.time()
        self._logger.info("market_data ws connected")
        self._subscribe_all()

    def _on_close(self, *_args) -> None:
        self._connected = False
        self._logger.info("market_data ws closed")

    def _on_error(self, _ws, error) -> None:
        self._logger.error("market_data ws error %s", error)

    def _subscribe_all(self) -> None:
        if not self._ws:
            return
        # 등록된 콜백 기반 구독 + 기본 ticker 구독
        topics = list(self._callbacks.keys())
        if not topics:
            # 기본 ticker 구독
            topics = [f"tickers.{s}" for s in self._symbols]
        sub_msg = {"op": "subscribe", "args": topics}
        self._ws.send(json.dumps(sub_msg))

    def _handle_message(self, _, message: str) -> None:
        self._last_msg_ts = time.time()
        try:
            data = json.loads(message)
        except json.JSONDecodeError:
            return

        topic: str = data.get("topic", "")

        # 콜백 딕셔너리에서 핸들러 탐색
        for key, cb in self._callbacks.items():
            if topic.startswith(key.split(".")[0]) and cb is not None:
                try:
                    cb(data)
                except Exception as exc:
                    self._logger.error("ws callback error topic=%s error=%s", topic, exc)

        # market_data_manager on_message 라우팅
        if ".ticker." in topic or topic.startswith("tickers."):
            channel = "ticker"
        elif "orderbook" in topic:
            channel = "orderbook"
        elif "publicTrade" in topic:
            channel = "trade"
        else:
            return

        payload_list = data.get("data")
        if isinstance(payload_list, list) and payload_list:
            payload = payload_list[0]
        elif isinstance(payload_list, dict):
            payload = payload_list
        else:
            return

        symbol = payload.get("symbol") or data.get("data", {}).get("s")
        if not symbol:
            # ticker 는 topic 에서 심볼 추출
            parts = topic.split(".")
            symbol = parts[-1] if parts else None
        if not symbol:
            return

        self._last_symbol_ts[symbol] = time.time()
        self._on_message_cb(symbol, channel, payload)

    # ──────────────────────────────────────────────────────────
    # Status
    # ──────────────────────────────────────────────────────────

    def is_connected(self) -> bool:
        if not self._connected:
            return False
        elapsed_ms = (time.time() - self._last_msg_ts) * 1000
        if elapsed_ms > 30_000:
            return False
        return True

