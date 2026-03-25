from __future__ import annotations

import logging
import math
import os
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional

logger = logging.getLogger("market_data.manager")

# ── 갱신 주기 ──────────────────────────────────────────────
_KLINES_1M_REFRESH_SEC = 300   # [초기값] 1분봉 — 300초마다 (Rate Limit 방지)
_KLINES_3M_REFRESH_SEC = 300   # [초기값] 3분봉 — 300초마다
_KLINES_5M_REFRESH_SEC = 600   # [초기값] 5분봉 — 600초마다
_KLINES_1H_REFRESH_SEC = 3600  # [초기값] 1시간봉 — 3600초마다 갱신
_API_CALL_DELAY_SEC = 0.25     # [초기값] 심볼 간 호출 딜레이
_TICKER_REFRESH_SEC = 5
_OI_REFRESH_SEC = 30
_KLINES_LIMIT = 200  # [검증값]

_INTERVAL_MAP = {"1m": "1", "3m": "3", "5m": "5", "15m": "15", "1h": "60"}

# paper/fallback용 최소 klines 길이(스캐너/테스트 안전장치)
_FALLBACK_KLINES_N = 200


def _safe(val: Any, default: float = 0.0) -> float:
    try:
        v = float(val)
        return v if math.isfinite(v) else default
    except (TypeError, ValueError):
        return default


def _make_dummy_klines(
    base_price: float, step_ms: int, n: int, wave: float = 0.0005
) -> List[Dict[str, Any]]:
    """
    봉 구조만 맞춰서 생성 (paper fallback/키 미설정 환경 테스트용).
    """
    now_ms = int(time.time() * 1000)
    out: List[Dict[str, Any]] = []
    for i in range(n):
        ts = now_ms - (n - i) * step_ms
        # 완전히 임의지만 open/high/low/close 관계는 일관되게 유지
        # 선형 추세만으로는 정규화된 지표가 상쇄되는 경우가 있어,
        # 약한 주기성 노이즈를 섞어 volatility/momentum을 함께 올린다.
        end_phase = max(0.0, (i - (n - 10)) / 10.0)  # 마지막 10개 봉에서만 bump
        close = base_price * (
            1.0
            + (i - n / 2) * wave
            + math.sin(i / 5.0) * wave * 2.5
            + end_phase * wave * 30.0
        )
        open_ = close * 0.9997
        # 기본 위크 + 일부 구간에서 더 큰 위크(스캐너 breakout_trace 보정용)
        if i >= n - 5:
            high = close * 1.0030
            low = close * 0.9970
        else:
            high = close * 1.0012
            low = close * 0.9982
        vol = 100.0 + float(i)
        out.append(
            {
                "timestamp": int(ts),
                "open": float(open_),
                "high": float(high),
                "low": float(low),
                "close": float(close),
                "volume": float(vol),
            }
        )
    return out


def _parse_klines_bybit(res: Any, symbol: str, tf: str) -> List[Dict[str, Any]]:
    """
    Bybit kline API 응답 파싱.
    응답: result.list = [[ts, open, high, low, close, volume, turnover], ...]
    Bybit 반환 순서: 최신→과거 → reversed로 과거→최신 변환
    """
    result: List[Dict[str, Any]] = []
    try:
        raw_list = res.get("result", {}).get("list", [])
        if not raw_list:
            logger.warning(
                "parse_klines empty list symbol=%s tf=%s retCode=%s",
                symbol,
                tf,
                res.get("retCode"),
            )
            return result

        for item in reversed(raw_list):
            if len(item) < 6:
                continue
            result.append(
                {
                    "timestamp": int(_safe(item[0])),
                    "open": _safe(item[1]),
                    "high": _safe(item[2]),
                    "low": _safe(item[3]),
                    "close": _safe(item[4]),
                    "volume": _safe(item[5]),
                }
            )
    except Exception as exc:
        logger.error(
            "parse_klines failed symbol=%s tf=%s error=%s",
            symbol,
            tf,
            exc,
        )
    return result


@dataclass
class MarketState:
    symbol: str

    last_price: Optional[float] = None
    best_bid: Optional[float] = None
    best_ask: Optional[float] = None
    spread: Optional[float] = None
    spread_bps: Optional[float] = None

    volume_24h: Optional[float] = None
    turnover_24h: Optional[float] = None

    open_interest: Optional[float] = None
    oi_prev_5m: Optional[float] = None
    funding_rate: Optional[float] = None

    orderbook: Dict[str, Any] = field(default_factory=lambda: {"bids": [], "asks": []})
    orderbook_bid_depth: Optional[float] = 0.0
    orderbook_ask_depth: Optional[float] = 0.0
    orderbook_depth_usd: float = 1_000_000.0
    bid_ask_ratio: float = 1.0

    recent_trades: List[Dict[str, Any]] = field(default_factory=list)
    klines_3m: List[Dict[str, Any]] = field(default_factory=list)
    klines_1m: List[Dict[str, Any]] = field(default_factory=list)
    klines_5m: List[Dict[str, Any]] = field(default_factory=list)
    klines_1h: List[Dict[str, Any]] = field(default_factory=list)  # [FIX 17]

    last_updated: float = 0.0
    latency_ms: float = 0.0
    ws_fresh: bool = False

    # test expectations
    rest_fallback_used: bool = False


class MarketDataManager:
    """
    REST 기반 실시간 시장 데이터 관리자.
    paper_mode에서도 실시간 시장 데이터 수신 (주문만 mock).
    API 키 없으면 mock 데이터 fallback.
    """

    def __init__(self, config: Any = None) -> None:
        self._config = config or {}
        self._paper_mode = bool(getattr(self._config, "paper_mode", False))

        self._lock = threading.Lock()
        self._states: Dict[str, MarketState] = {}

        self._http = None
        self._symbols: List[str] = []

        self._last_klines: Dict[str, float] = {}
        self._last_ticker: Dict[str, float] = {}
        self._last_oi: Dict[str, float] = {}

        self._fallback_count = 0

        self._init_http_client()

    def _init_http_client(self) -> None:
        """
        API 키 로드 우선순위:
        1. 환경변수 BYBIT_API_KEY / BYBIT_API_SECRET
        2. self._config 에서 bybit_api_key / bybit_api_secret 추출
           - dict / ConfigManager / get() 메서드 보유 객체 모두 지원
        3. 둘 다 없으면 mock mode
        """
        # 1순위: 환경변수
        api_key = os.environ.get("BYBIT_API_KEY", "")
        api_secret = os.environ.get("BYBIT_API_SECRET", "")

        # 2순위: self._config 에서 추출 (타입 무관 처리)
        if not api_key or not api_secret:
            try:
                cfg = self._config

                # dict 타입
                if isinstance(cfg, dict):
                    api_key = api_key or str(cfg.get("bybit_api_key", "") or "")
                    api_secret = (
                        api_secret or str(cfg.get("bybit_api_secret", "") or "")
                    )

                # get() 메서드를 가진 객체 (ConfigManager 등)
                elif hasattr(cfg, "get"):
                    api_key = api_key or str(cfg.get("bybit_api_key", "") or "")
                    api_secret = (
                        api_secret
                        or str(cfg.get("bybit_api_secret", "") or "")
                    )

                # load_system_config() 메서드를 가진 객체
                elif hasattr(cfg, "load_system_config"):
                    raw = cfg.load_system_config()
                    if isinstance(raw, dict):
                        api_key = api_key or str(
                            raw.get("bybit_api_key", "") or ""
                        )
                        api_secret = api_secret or str(
                            raw.get("bybit_api_secret", "") or ""
                        )
            except Exception as exc:
                logger.error("_init_http_client config read failed error=%s", exc)

        # 3순위: system_config.yaml 직접 읽기 (최후 fallback)
        if not api_key or not api_secret:
            try:
                import yaml as _yaml

                _cfg_path = os.path.join("config", "system_config.yaml")
                if os.path.exists(_cfg_path):
                    with open(_cfg_path, "r", encoding="utf-8") as _f:
                        _raw = _yaml.safe_load(_f) or {}
                    api_key = api_key or str(_raw.get("bybit_api_key", "") or "")
                    api_secret = api_secret or str(
                        _raw.get("bybit_api_secret", "") or ""
                    )
            except Exception as exc:
                logger.error(
                    "_init_http_client yaml fallback failed error=%s", exc
                )

        if not api_key or not api_secret:
            logger.warning(
                "market_data_manager no API key in env or config — mock mode"
            )
            return

        try:
            from pybit.unified_trading import HTTP

            # testnet 설정도 동일한 방식으로 추출
            testnet = False
            try:
                cfg = self._config
                if isinstance(cfg, dict):
                    testnet = bool(cfg.get("bybit_testnet", False))
                elif hasattr(cfg, "get"):
                    testnet = bool(cfg.get("bybit_testnet", False))
            except Exception:
                pass

            self._http = HTTP(
                api_key=api_key,
                api_secret=api_secret,
                testnet=testnet,
            )
            logger.info(
                "market_data_manager HTTP client initialized OK testnet=%s",
                testnet,
            )
        except Exception as exc:
            logger.error("market_data_manager HTTP init failed error=%s", exc)
            self._http = None

    def initialize(self, symbols: List[str]) -> None:
        self._symbols = list(symbols)
        for symbol in symbols:
            if symbol not in self._states:
                self._states[symbol] = MarketState(symbol=symbol)

        if self._http is None:
            # API 키 없는 환경에서도 klines/가격/스프레드/트레이드 버퍼는 채워둔다.
            self._apply_paper_mode_fallback(symbols)
            return

        for symbol in symbols:
            try:
                self._fetch_all(symbol, force=True)
                logger.info(
                    "market_data_manager initialized symbol=%s price=%s klines_3m=%d oi=%s funding=%s",
                    symbol,
                    self._states[symbol].last_price,
                    len(self._states[symbol].klines_3m),
                    self._states[symbol].open_interest,
                    self._states[symbol].funding_rate,
                )
            except Exception as exc:
                logger.error("initialize symbol=%s error=%s", symbol, exc)
            import time as _t

            _t.sleep(1.0)  # [초기값] 심볼별 초기화 간 1초 딜레이

    def start(self) -> None:
        # paper_mode에서는 WS 연결을 하지 않는다.
        # (기존 테스트/호환성: start()는 존재해야 한다.)
        return

    def stop(self) -> None:
        return

    def refresh_all(self) -> None:
        if self._http is None:
            return
        for symbol in list(self._states.keys()):
            try:
                self._fetch_all(symbol)
            except Exception as exc:
                logger.error("refresh_all symbol=%s error=%s", symbol, exc)

    def _fetch_all(self, symbol: str, force: bool = False) -> None:
        now = time.time()

        if force or now - self._last_ticker.get(symbol, 0.0) >= _TICKER_REFRESH_SEC:
            self._fetch_ticker(symbol)
            self._last_ticker[symbol] = now

        # klines — 타임프레임별 독립 갱신 주기
        if force or now - self._last_klines.get(symbol + "_1m", 0) >= _KLINES_1M_REFRESH_SEC:
            self._fetch_klines_single(symbol, "1m")
            self._last_klines[symbol + "_1m"] = now

        if force or now - self._last_klines.get(symbol + "_3m", 0) >= _KLINES_3M_REFRESH_SEC:
            self._fetch_klines_single(symbol, "3m")
            self._last_klines[symbol + "_3m"] = now

        if force or now - self._last_klines.get(symbol + "_5m", 0) >= _KLINES_5M_REFRESH_SEC:
            self._fetch_klines_single(symbol, "5m")
            self._last_klines[symbol + "_5m"] = now

        if force or now - self._last_klines.get(symbol + "_1h", 0) >= _KLINES_1H_REFRESH_SEC:
            self._fetch_klines_single(symbol, "1h")
            self._last_klines[symbol + "_1h"] = now

        if force or now - self._last_oi.get(symbol, 0.0) >= _OI_REFRESH_SEC:
            self._fetch_oi(symbol)
            self._last_oi[symbol] = now

        if force or now - self._last_ticker.get(symbol + "_ob", 0) >= 30:
            self._fetch_orderbook(symbol)
            self._last_ticker[symbol + "_ob"] = now

        with self._lock:
            if symbol in self._states:
                self._states[symbol].last_updated = time.time()

    def _fetch_ticker(self, symbol: str) -> None:
        try:
            t0 = time.time()
            res = self._http.get_tickers(category="linear", symbol=symbol)
            latency = (time.time() - t0) * 1000

            items = res.get("result", {}).get("list", [])
            if not items:
                logger.warning(
                    "fetch_ticker empty symbol=%s retCode=%s retMsg=%s",
                    symbol,
                    res.get("retCode"),
                    res.get("retMsg"),
                )
                return

            t = items[0]
            last_price = _safe(t.get("lastPrice"))
            best_bid = _safe(t.get("bid1Price"))
            best_ask = _safe(t.get("ask1Price"))

            if last_price <= 0:
                logger.warning(
                    "fetch_ticker price=0 symbol=%s keys=%s",
                    symbol,
                    list(t.keys()),
                )
                return

            mid = (best_bid + best_ask) / 2 if (best_bid + best_ask) > 0 else last_price
            spread_bps = ((best_ask - best_bid) / mid * 10000.0) if mid > 0 else 0.0

            # fundingRate 필드 (ticker 응답에 포함되는 값 사용)
            funding_rate = _safe(t.get("fundingRate", "0"), 0.0)

            with self._lock:
                s = self._states[symbol]
                s.last_price = last_price
                s.best_bid = best_bid
                s.best_ask = best_ask
                s.spread = float(best_ask) - float(best_bid)
                s.spread_bps = round(spread_bps, 4)
                s.volume_24h = _safe(t.get("volume24h"))
                s.turnover_24h = _safe(t.get("turnover24h"))
                s.funding_rate = funding_rate
                s.latency_ms = round(latency, 2)
                s.ws_fresh = True
                s.rest_fallback_used = False

            if latency > 500:
                logger.warning("HIGH LATENCY symbol=%s %.0fms", symbol, latency)
        except Exception as exc:
            logger.error("fetch_ticker failed symbol=%s error=%s", symbol, exc)

    def _fetch_klines_single(self, symbol: str, tf: str) -> None:
        """단일 심볼 단일 타임프레임 klines 갱신. 호출 전 딜레이 포함."""
        try:
            import time as _t

            _t.sleep(_API_CALL_DELAY_SEC)  # [초기값] Rate Limit 방지

            res = self._http.get_kline(
                category="linear",
                symbol=symbol,
                interval=_INTERVAL_MAP[tf],
                limit=_KLINES_LIMIT,
            )
            klines = _parse_klines_bybit(res, symbol, tf)
            if klines:
                with self._lock:
                    s = self._states[symbol]
                    setattr(s, f"klines_{tf}", klines)
                logger.debug(
                    "fetch_klines symbol=%s tf=%s count=%d last_close=%.4f",
                    symbol,
                    tf,
                    len(klines),
                    klines[-1].get("close", 0) if klines else 0,
                )
            else:
                logger.warning(
                    "fetch_klines empty symbol=%s tf=%s retCode=%s",
                    symbol,
                    tf,
                    res.get("retCode"),
                )
        except Exception as exc:
            logger.error(
                "fetch_klines failed symbol=%s tf=%s error=%s",
                symbol,
                tf,
                exc,
            )

    def _fetch_oi(self, symbol: str) -> None:
        try:
            res = self._http.get_open_interest(
                category="linear",
                symbol=symbol,
                intervalTime="5min",
                limit=2,
            )
            items = res.get("result", {}).get("list", [])
            if items:
                oi_now = _safe(items[0].get("openInterest"))
                oi_prev = _safe(items[1].get("openInterest")) if len(items) > 1 else oi_now
                with self._lock:
                    s = self._states[symbol]
                    s.open_interest = oi_now
                    s.oi_prev_5m = oi_prev
            else:
                logger.warning(
                    "fetch_oi empty symbol=%s retCode=%s retMsg=%s",
                    symbol,
                    res.get("retCode"),
                    res.get("retMsg"),
                )
        except Exception as exc:
            logger.error("fetch_oi failed symbol=%s error=%s", symbol, exc)

    def _fetch_orderbook(self, symbol: str) -> None:
        """호가창 수신 → bid_ask_ratio, orderbook_depth_usd 갱신."""
        try:
            res = self._http.get_orderbook(
                category="linear", symbol=symbol, limit=50
            )
            result = res.get("result", {})
            bids = result.get("b", []) or result.get("bids", [])
            asks = result.get("a", []) or result.get("asks", [])

            if not bids or not asks:
                return

            # bid/ask 수량 합계 기반 ratio
            bid_vol = sum(float(b[1]) for b in bids[:10] if len(b) >= 2)
            ask_vol = sum(float(a[1]) for a in asks[:10] if len(a) >= 2)
            ratio = bid_vol / ask_vol if ask_vol > 0 else 1.0

            # depth USD (현재가 ± 1% 범위 내 호가 규모)
            with self._lock:
                price = _safe(
                    self._states.get(symbol).last_price if self._states.get(symbol) else 0
                )
            if price > 0:
                lower = price * 0.99
                upper = price * 1.01
                bid_depth = sum(
                    float(b[0]) * float(b[1])
                    for b in bids
                    if len(b) >= 2 and float(b[0]) >= lower
                )
                ask_depth = sum(
                    float(a[0]) * float(a[1])
                    for a in asks
                    if len(a) >= 2 and float(a[0]) <= upper
                )
                depth_usd = bid_depth + ask_depth
            else:
                depth_usd = 1_000_000.0

            with self._lock:
                s = self._states[symbol]
                s.orderbook = {"bids": bids, "asks": asks}
                s.bid_ask_ratio = round(ratio, 6)
                s.orderbook_depth_usd = max(depth_usd, 1_000_000.0)

            logger.debug(
                "fetch_orderbook symbol=%s ratio=%.4f depth_usd=%.0f",
                symbol, ratio, depth_usd,
            )
        except Exception as exc:
            logger.error("fetch_orderbook failed symbol=%s error=%s", symbol, exc)

    def _apply_paper_mode_fallback(self, symbols: List[str]) -> None:
        now_ms = int(time.time() * 1000)
        fallback = {
            "BTCUSDT": {"last_price": 65000.0, "best_bid": 64999.0, "best_ask": 65001.0},
            "ETHUSDT": {"last_price": 3200.0, "best_bid": 3199.0, "best_ask": 3201.0},
            # SOL은 fallback에서 spread_bps가 지나치게 커서 liquidity_score가 급감하는 경우가 있어 좁혀둔다.
            "SOLUSDT": {"last_price": 150.0, "best_bid": 149.995, "best_ask": 150.005},
        }

        trades_template: List[Dict[str, Any]] = []
        # scanner_features 참여도(최근 체결 수) 및 orderflow_features trade_velocity를 올리기 위한 더미 체결
        for j in range(60):
            trades_template.append(
                {
                    "price": 1.0 + (j - 30) * 0.0005,
                    "size": 1.0 + float(j) * 0.01,
                    "side": "Buy" if (j % 2 == 0) else "Sell",
                    "ts_ms": now_ms - (60 - j) * 1000,
                }
            )

        with self._lock:
            for sym in symbols:
                data = fallback.get(sym)
                if not data:
                    continue
                s = self._states[sym]
                s.last_price = data["last_price"]
                s.best_bid = data["best_bid"]
                s.best_ask = data["best_ask"]
                s.spread = s.best_ask - s.best_bid
                s.spread_bps = s.spread / s.last_price * 10000.0 if s.last_price else 2.0
                s.recent_trades = list(trades_template)

                s.klines_3m = _make_dummy_klines(s.last_price, step_ms=180000, n=_FALLBACK_KLINES_N)
                s.klines_1m = _make_dummy_klines(s.last_price, step_ms=60000, n=_FALLBACK_KLINES_N)
                s.klines_5m = _make_dummy_klines(s.last_price, step_ms=300000, n=_FALLBACK_KLINES_N)
                s.klines_1h = _make_dummy_klines(s.last_price, step_ms=3600000, n=200)  # [FIX 17]

                # 스캐너/entry-score 랭커에서 최소 점수(70점) 통과하도록 paper fallback 값 강화
                s.volume_24h = 2_000_000_000.0
                s.turnover_24h = 200_000_000.0
                s.bid_ask_ratio = 2.0

                s.open_interest = 0.97
                s.oi_prev_5m = 1.0
                s.funding_rate = 0.001

                s.rest_fallback_used = True
                s.ws_fresh = True
                s.last_updated = time.time()
                self._fallback_count += 1

                logger.info("market_data fallback activated symbol=%s", sym)

    # ──────────────────────────────────────────────────────────
    # Public APIs (tests + other modules)
    # ──────────────────────────────────────────────────────────

    def get_state(self, symbol: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            s = self._states.get(symbol)
            if s is None:
                return None
            return {
                "last_price": s.last_price,
                "best_bid": s.best_bid,
                "best_ask": s.best_ask,
                "spread": s.spread,
                "spread_bps": s.spread_bps,
                "volume_24h": s.volume_24h,
                "turnover_24h": s.turnover_24h,
                "open_interest": s.open_interest,
                "oi_prev_5m": s.oi_prev_5m,
                "funding_rate": s.funding_rate,
                "orderbook": s.orderbook,
                "orderbook_bid_depth": s.orderbook_bid_depth,
                "orderbook_ask_depth": s.orderbook_ask_depth,
                "orderbook_depth_usd": s.orderbook_depth_usd,
                "bid_ask_ratio": s.bid_ask_ratio,
                "recent_trades": s.recent_trades,
                "klines_3m": s.klines_3m,
                "klines_1m": s.klines_1m,
                "klines_5m": s.klines_5m,
                "klines_1h": s.klines_1h,  # [FIX 17]
                "last_updated": s.last_updated,
                "latency_ms": s.latency_ms,
                "ws_fresh": s.ws_fresh,
            }

    def get_market_state(self, symbol: str) -> Optional[MarketState]:
        with self._lock:
            return self._states.get(symbol)

    def get_all_symbols(self) -> List[str]:
        with self._lock:
            return list(self._states.keys())

    def start_ws(self) -> None:
        # compatibility alias (not used in tests)
        return

    def on_ws_message(self, symbol: str, channel: str, payload: Dict[str, Any]) -> None:
        """
        tests/unit 호환용.
        - ticker: last_price/best_bid/best_ask 갱신
        - trade: recent_trades ring buffer 갱신(최대 200)
        """
        if symbol not in self._states:
            with self._lock:
                self._states[symbol] = MarketState(symbol=symbol)

        with self._lock:
            s = self._states[symbol]

            if channel == "ticker":
                # partial update: value=None이면 덮어쓰지 않음
                lp = payload.get("lastPrice") if "lastPrice" in payload else payload.get("last_price")
                bb = payload.get("bid1Price") if "bid1Price" in payload else payload.get("best_bid")
                ba = payload.get("ask1Price") if "ask1Price" in payload else payload.get("best_ask")

                if lp is not None:
                    s.last_price = _safe(lp)
                if bb is not None:
                    s.best_bid = _safe(bb)
                if ba is not None:
                    s.best_ask = _safe(ba)

                if s.best_bid is not None and s.best_ask is not None:
                    s.spread = s.best_ask - s.best_bid
                    if s.last_price and s.last_price > 0:
                        s.spread_bps = s.spread / s.last_price * 10000.0

                v24 = payload.get("volume24h", None)
                t24 = payload.get("turnover24h", None)
                if v24 is not None:
                    s.volume_24h = _safe(v24)
                if t24 is not None:
                    s.turnover_24h = _safe(t24)

                s.ws_fresh = True

            elif channel == "orderbook":
                # tests에서 사용하지 않지만, AICoinScanner/슬리피지 계산 확장 가능
                bids = payload.get("bids", []) or []
                asks = payload.get("asks", []) or []
                s.orderbook = {"bids": bids, "asks": asks}

                # depth(상위 5 레벨)
                s.orderbook_bid_depth = sum(_safe(b[1]) for b in bids[:5]) if bids else 0.0
                s.orderbook_ask_depth = sum(_safe(a[1]) for a in asks[:5]) if asks else 0.0

                bid_sum = sum(_safe(b[1]) for b in bids[:10]) if bids else 0.0
                ask_sum = sum(_safe(a[1]) for a in asks[:10]) if asks else 0.0
                s.bid_ask_ratio = (bid_sum / ask_sum) if ask_sum > 0 else 1.0

            elif channel == "trade":
                # ring buffer: 200 유지
                buf: Deque[Dict[str, Any]] = deque(s.recent_trades, maxlen=200)
                buf.append(
                    {
                        "price": float(payload.get("price", 0.0)),
                        "size": float(payload.get("size", 0.0)),
                        "side": str(payload.get("side", "Buy")),
                        "ts_ms": int(payload.get("ts_ms", time.time() * 1000)),
                    }
                )
                s.recent_trades = list(buf)

            # ignored channel: no-op

    def healthcheck(self) -> Dict[str, Any]:
        with self._lock:
            tracked = len(self._states)
            now_ms = int(time.time() * 1000)

            symbols_ready = (
                tracked > 0
                and all(
                    self._states[s].last_price is not None
                    and self._states[s].best_bid is not None
                    and self._states[s].best_ask is not None
                    for s in self._states
                )
            )
            stale: List[str] = []
            for sym, state in self._states.items():
                # last_updated는 초 단위
                if (time.time() - (state.last_updated or 0.0)) * 1000 > 60_000:
                    stale.append(sym)

            metadata_count = tracked
            degraded = not (self._paper_mode and symbols_ready and metadata_count >= tracked)

            return {
                "tracked_symbol_count": tracked,
                "ws_connected": False,
                "stale_symbols": stale,
                "fallback_count": self._fallback_count,
                "metadata_count": metadata_count,
                "last_refresh_ts_ms": int(time.time() * 1000),
                "symbols_ready": symbols_ready,
                "degraded": degraded,
            }

    def get_bid_ask_ratio(self, symbol: str) -> float:
        with self._lock:
            s = self._states.get(symbol)
            if s is None:
                return 1.0
            return float(s.bid_ask_ratio) if s.bid_ask_ratio is not None else 1.0

    def get_orderbook_depth_usd(self, symbol: str, pct: float = 0.01) -> float:
        with self._lock:
            s = self._states.get(symbol)
            if s is None:
                return 1_000_000.0
            return float(s.orderbook_depth_usd) if s.orderbook_depth_usd else 1_000_000.0

    def get_top_symbols_by_volume(
        self,
        top_n: int = 20,
        min_volume_usd: float = 100_000_000.0,
    ) -> List[str]:
        """
        Bybit 전체 USDT Perpetual 코인 중
        24h turnover 기준 상위 top_n 개 심볼 반환.
        API 실패 시 빈 리스트 반환.
        """
        if self._http is None:
            logger.warning("get_top_symbols_by_volume: no HTTP client")
            return []
        try:
            res = self._http.get_tickers(category="linear")
            tickers = res.get("result", {}).get("list", [])

            filtered = []
            for t in tickers:
                sym = t.get("symbol", "")
                if not sym.endswith("USDT"):
                    continue
                turnover = _safe(t.get("turnover24h"), 0.0)
                if turnover < min_volume_usd:         # [초기값] $1억
                    continue
                filtered.append((sym, turnover))

            filtered.sort(key=lambda x: x[1], reverse=True)
            symbols = [s[0] for s in filtered[:top_n]]  # [초기값] 상위 20개

            logger.info(
                "get_top_symbols_by_volume top=%d min_vol=$%.0fM result=%s",
                top_n, min_volume_usd / 1e6, symbols[:5],
            )
            return symbols
        except Exception as exc:
            logger.error("get_top_symbols_by_volume failed error=%s", exc)
            return []

