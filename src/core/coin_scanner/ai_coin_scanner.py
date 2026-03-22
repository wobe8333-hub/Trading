from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.core.coin_scanner.coin_classifier import CoinClassifier
from src.core.coin_scanner.macro_coin_selector import MacroCoinSelector
from src.core.coin_scanner.scanner_features import ScannerFeatureCalculator
from src.core.coin_scanner.scanner_ranker import ScannerRanker
from src.core.coin_scanner.scanner_state import ScannerState

logger = logging.getLogger("scanner.ai")

_LOG_DIR = "logs/scanner"


class AICoinScanner:
    """
    전체 스캐너 파이프라인 오케스트레이터.
    """

    def __init__(
        self,
        market_data_manager: Optional[Any] = None,
        config: Optional[Any] = None,
        macro_state: str = "NEUTRAL",
    ) -> None:
        self._mdm = market_data_manager
        self._config = config
        self._macro_state = macro_state

        self._feature_calc = ScannerFeatureCalculator()
        self._ranker = ScannerRanker()
        self._classifier = CoinClassifier(config)
        self._selector = MacroCoinSelector()
        self._state = ScannerState()

        os.makedirs(_LOG_DIR, exist_ok=True)

    def set_macro_state(self, macro_state: str) -> None:
        self._macro_state = macro_state

    def scan(self, mdm=None):
        # 외부 MDM 주입 지원 — trading_loop의 실시간 MDM 사용
        _mdm = mdm if mdm is not None else self._mdm
        try:
            return self._run_pipeline(_mdm=_mdm)
        except Exception as exc:
            logger.error("ai_coin_scanner scan failed error=%s", exc)
            return []

    def _run_pipeline(self, _mdm: Optional[Any] = None) -> List[Dict[str, Any]]:
        t_start = time.time()
        symbols = self._get_symbols(_mdm=_mdm)
        if not symbols:
            logger.warning("ai_coin_scanner no symbols available")
            return []

        features: Dict[str, Dict[str, Any]] = {}
        market_states: Dict[str, Dict[str, Any]] = {}
        for sym in symbols:
            ms = self._get_market_state(sym, _mdm=_mdm)
            market_states[sym] = ms
            feat = self._feature_calc.compute_all_features(sym, ms)
            features[sym] = feat

        ranked = self._ranker.rank_all(features)

        btc_state = market_states.get("BTCUSDT", {})
        btc_klines = btc_state.get("klines_1m") or []
        btc_closes = [float(k.get("close", 0)) for k in btc_klines if k.get("close")]
        btc_returns: List[float] = []
        for i in range(1, len(btc_closes)):
            if btc_closes[i - 1] > 0:
                import math
                btc_returns.append(math.log(btc_closes[i] / btc_closes[i - 1]))

        coin_types = self._classifier.classify_all(
            symbols, btc_returns, market_states
        )

        top3 = self._selector.select_top3(ranked, coin_types, self._macro_state)

        self._state.update(
            top3=top3,
            full_ranking=ranked,
            coin_types=coin_types,
            macro_state=self._macro_state,
        )

        elapsed = round((time.time() - t_start) * 1000, 1)
        self._log_result(top3, ranked, elapsed)

        return top3

    def _get_symbols(self, _mdm: Optional[Any] = None) -> List[str]:
        if _mdm is not None:
            try:
                return _mdm.get_all_symbols()
            except Exception as exc:
                logger.error("get_all_symbols failed: %s", exc)
        return ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

    def _get_market_state(self, symbol: str, _mdm: Optional[Any] = None) -> Dict[str, Any]:
        if _mdm is not None:
            try:
                state = _mdm.get_state(symbol)
                if state and isinstance(state, dict):
                    state.setdefault(
                        "bid_ask_ratio",
                        _mdm.get_bid_ask_ratio(symbol),
                    )
                    state.setdefault(
                        "orderbook_depth_usd",
                        _mdm.get_orderbook_depth_usd(symbol),
                    )
                    return state
            except Exception as exc:
                logger.error("get_market_state failed symbol=%s: %s", symbol, exc)
        return {}

    def _log_result(
        self,
        top3: List[Dict[str, Any]],
        ranked: List[Dict[str, Any]],
        elapsed_ms: float,
    ) -> None:
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        lines = [
            f"[{now_str}] scan elapsed={elapsed_ms}ms macro={self._macro_state}",
            f"  TOP3: {[r['symbol'] for r in top3]}",
            f"  scores: {[r['score'] for r in top3]}",
            f"  types: {[r.get('coin_type','?') for r in top3]}",
            f"  full_ranking_count: {len(ranked)}",
        ]
        log_line = "\n".join(lines) + "\n"
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        log_path = os.path.join(_LOG_DIR, f"{today}.log")
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(log_line)
        except Exception as exc:
            logger.error("scanner log write failed: %s", exc)
        logger.info("ai_coin_scanner scan done top3=%s", [r["symbol"] for r in top3])
