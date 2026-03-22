from __future__ import annotations

import math
from dataclasses import dataclass, asdict
from threading import Lock
from time import time_ns
from typing import Any, Dict, Optional


@dataclass
class SymbolMetadata:
    symbol: str
    tick_size: float
    qty_step: float
    min_order_qty: float
    min_notional: float
    price_scale: int
    base_coin: str
    quote_coin: str
    status: str
    updated_ts_ms: int


class SymbolMetadataStore:
    """
    tick_size / qty_step / min_order_qty 캐시 스토어.
    load_all() 로 전체 로드, 개별 getter 및 round 유틸 제공.
    """

    def __init__(self) -> None:
        self._store: Dict[str, SymbolMetadata] = {}
        self._lock = Lock()

    # ──────────────────────────────────────────────────────────
    # CRUD
    # ──────────────────────────────────────────────────────────

    def get(self, symbol: str) -> Optional[SymbolMetadata]:
        with self._lock:
            return self._store.get(symbol)

    def set(self, metadata: SymbolMetadata) -> None:
        with self._lock:
            self._store[metadata.symbol] = metadata

    def bulk_set(self, items: Dict[str, Dict[str, Any]]) -> None:
        now_ms = int(time_ns() / 1_000_000)
        with self._lock:
            for symbol, data in items.items():
                self._store[symbol] = SymbolMetadata(
                    symbol=symbol,
                    tick_size=float(data["tick_size"]),
                    qty_step=float(data["qty_step"]),
                    min_order_qty=float(data["min_order_qty"]),
                    min_notional=float(data.get("min_notional", 0.0)),
                    price_scale=int(data.get("price_scale", 2)),
                    base_coin=str(data.get("base_coin", "")),
                    quote_coin=str(data.get("quote_coin", "USDT")),
                    status=str(data.get("status", "Trading")),
                    updated_ts_ms=int(data.get("updated_ts_ms", now_ms)),
                )

    def has(self, symbol: str) -> bool:
        with self._lock:
            return symbol in self._store

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def to_dict(self) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            return {sym: asdict(meta) for sym, meta in self._store.items()}

    def count(self) -> int:
        with self._lock:
            return len(self._store)

    # ──────────────────────────────────────────────────────────
    # 명세 요구 메서드
    # ──────────────────────────────────────────────────────────

    def load_all(self, rest_client=None) -> Dict[str, Dict[str, Any]]:
        """
        rest_client 가 제공되면 전체 instruments_info 를 로드한다.
        paper_mode 등 테스트 환경에서는 rest_client=None 으로 호출하면
        현재 캐시를 그대로 반환한다.
        """
        if rest_client is not None:
            raw = rest_client.get_instruments_info([])
            items = raw.get("list", [])
            for item in items:
                sym = item.get("symbol", "")
                lot = item.get("lotSizeFilter", {})
                price_filter = item.get("priceFilter", {})
                self.bulk_set({
                    sym: {
                        "tick_size":      float(price_filter.get("tickSize", 0.01)),
                        "qty_step":       float(lot.get("qtyStep", 0.001)),
                        "min_order_qty":  float(lot.get("minOrderQty", 0.001)),
                        "min_notional":   float(lot.get("minNotionalValue", 5.0)),
                        "price_scale":    int(item.get("priceScale", 2)),
                        "base_coin":      str(item.get("baseCoin", "")),
                        "quote_coin":     str(item.get("quoteCoin", "USDT")),
                        "status":         str(item.get("status", "Trading")),
                    }
                })
        return self.to_dict()

    def get_tick_size(self, symbol: str) -> float:
        meta = self.get(symbol)
        if meta is None:
            raise KeyError(f"symbol_metadata not found: {symbol}")
        return meta.tick_size

    def get_qty_step(self, symbol: str) -> float:
        meta = self.get(symbol)
        if meta is None:
            raise KeyError(f"symbol_metadata not found: {symbol}")
        return meta.qty_step

    def get_min_order_qty(self, symbol: str) -> float:
        meta = self.get(symbol)
        if meta is None:
            raise KeyError(f"symbol_metadata not found: {symbol}")
        return meta.min_order_qty

    def round_price(self, symbol: str, price: float) -> float:
        """tick_size 기준 반올림."""
        tick = self.get_tick_size(symbol)
        return round(round(price / tick) * tick, 10)

    def round_qty(self, symbol: str, qty: float) -> float:
        """qty_step 기준 내림(floor)."""
        step = self.get_qty_step(symbol)
        return math.floor(qty / step) * step

