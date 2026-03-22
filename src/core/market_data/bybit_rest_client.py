from __future__ import annotations

import logging
import time
from typing import Any, Dict, List

logger = logging.getLogger("market_data")

# interval 매핑 [초기값]
_INTERVAL_MAP: Dict[str, str] = {
    "1m": "1", "3m": "3", "5m": "5", "15m": "15",
    "30m": "30", "1h": "60", "4h": "240", "1d": "D",
}


class BybitRestClient:
    """
    Bybit REST API thin wrapper (pybit v5).
    실제 pybit 클라이언트는 지연 로딩하여 테스트 시 네트워크/의존성에 묶이지 않도록 한다.
    """

    def __init__(
        self,
        api_key: str = "",
        api_secret: str = "",
        testnet: bool = False,
    ) -> None:
        self._api_key = api_key
        self._api_secret = api_secret
        self._testnet = testnet
        self._client = None
        self.kill_switch_signal: bool = False

    def _ensure_client(self) -> Any:
        if self._client is None:
            from pybit.unified_trading import HTTP
            self._client = HTTP(
                api_key=self._api_key,
                api_secret=self._api_secret,
                testnet=self._testnet,
            )
        return self._client

    def _call_with_retry(self, fn, *args, **kwargs) -> Any:
        """최대 3회 재시도 (1초 간격). 3회 실패 시 kill_switch_signal = True."""
        last_exc: Exception | None = None
        for attempt in range(3):
            try:
                return fn(*args, **kwargs)
            except Exception as exc:
                last_exc = exc
                logger.error("rest_client retry attempt=%d error=%s", attempt + 1, exc)
                time.sleep(1)
        self.kill_switch_signal = True
        logger.error("rest_client 3 retries failed, kill_switch_signal=True")
        raise RuntimeError(f"API call failed after 3 retries: {last_exc}") from last_exc

    def get_tickers(self, category: str = "linear") -> List[Dict[str, Any]]:
        client = self._ensure_client()
        res = self._call_with_retry(client.get_tickers, category=category)
        return res.get("result", {}).get("list", [])

    def get_orderbook(self, symbol: str, limit: int = 50) -> Dict[str, Any]:
        client = self._ensure_client()
        res = self._call_with_retry(
            client.get_orderbook, category="linear", symbol=symbol, limit=limit
        )
        return res.get("result", {})

    def get_klines(self, symbol: str, interval: str, limit: int = 200) -> List[Dict[str, Any]]:
        """
        interval 매핑: "1m"→"1", "3m"→"3", "5m"→"5", "15m"→"15"
        반환: [{open, high, low, close, volume, timestamp}, ...]
        """
        client = self._ensure_client()
        mapped = _INTERVAL_MAP.get(interval, interval)
        res = self._call_with_retry(
            client.get_kline,
            category="linear",
            symbol=symbol,
            interval=mapped,
            limit=limit,
        )
        raw_list = res.get("result", {}).get("list", [])
        # Bybit kline 반환: [timestamp, open, high, low, close, volume, turnover]
        result = []
        for row in raw_list:
            result.append({
                "timestamp": int(row[0]),
                "open":      float(row[1]),
                "high":      float(row[2]),
                "low":       float(row[3]),
                "close":     float(row[4]),
                "volume":    float(row[5]),
            })
        return result

    def get_open_interest(self, symbol: str, interval: str = "5min") -> Dict[str, Any]:
        client = self._ensure_client()
        res = self._call_with_retry(
            client.get_open_interest,
            category="linear",
            symbol=symbol,
            intervalTime=interval,
            limit=10,
        )
        return res.get("result", {})

    def get_funding_rate(self, symbol: str) -> float:
        """fundingRate 필드를 float 으로 반환한다."""
        client = self._ensure_client()
        res = self._call_with_retry(
            client.get_tickers, category="linear", symbol=symbol
        )
        items = res.get("result", {}).get("list", [])
        if items:
            return float(items[0].get("fundingRate", 0.0))
        return 0.0

    def get_instrument_info(self, symbol: str) -> Dict[str, Any]:
        """단일 심볼 instrument info 반환."""
        client = self._ensure_client()
        res = self._call_with_retry(
            client.get_instruments_info, category="linear", symbol=symbol
        )
        items = res.get("result", {}).get("list", [])
        if items:
            return items[0]
        return {}

    def get_instruments_info(self, symbols: List[str]) -> Dict[str, Any]:
        """복수 심볼 instruments info 반환 (하위 호환 유지)."""
        client = self._ensure_client()
        res = self._call_with_retry(
            client.get_instruments_info,
            category="linear",
            symbol=",".join(symbols),
        )
        return res.get("result", {})

    def measure_latency(self) -> float:
        """
        get_tickers 호출 전후 레이턴시(ms) 측정.
        500ms 초과 시 WARNING 로그. [검증값: 500ms]
        """
        t0 = time.time()
        self.get_tickers()
        latency_ms = (time.time() - t0) * 1000
        if latency_ms > 500:  # [검증값]
            logger.warning("rest_client latency=%.1fms exceeds 500ms threshold", latency_ms)
        else:
            logger.info("rest_client latency=%.1fms", latency_ms)
        return latency_ms

    def ping(self) -> bool:
        client = self._ensure_client()
        client.get_server_time()
        return True

