from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from src.app.state_store import StateStore
from src.utils.config_loader import ConfigManager
from src.core.market_data.market_data_manager import MarketDataManager
from src.core.time_filter.session_filter import SessionFilter
from src.core.macro_filter.macro_market_filter import MacroMarketFilter
from src.core.coin_scanner.ai_coin_scanner import AICoinScanner
from src.core.regime_engine.market_regime_engine import MarketRegimeEngine
from src.core.orderflow_engine.orderflow_engine import OrderflowEngine
from src.core.execution_cost_guard.cost_guard import ExecutionCostGuard
from src.strategy.selector.rule_based_selector import RuleBasedSelector
from src.strategy.selector.strategy_feedback import StrategyFeedback
from src.strategy.selector.strategy_weights import StrategyWeights
from src.strategy.entry_score.entry_score_engine import EntryScoreEngine
from src.growth.position_scaler import PositionScaler
from src.growth.account_growth_engine import AccountGrowthEngine
from src.risk.risk_engine import RiskEngine
from src.risk.drawdown_manager import DrawdownManager
from src.execution.execution_engine import ExecutionEngine
from src.execution.order_router import OrderRouter
from src.analytics.analytics_engine import AnalyticsEngine
from src.analytics.target_tracker import TargetTracker
from src.utils.math_utils import compute_atr

logger = logging.getLogger("app.trading_loop")

_LOOP_SLEEP_SEC = 3  # [초기값] 루프 주기
_SCAN_INTERVAL = 60  # [검증값] 코인 스캔 주기(초)
_SESSION_SLEEP = 30  # [초기값] 세션 외 대기
_KILL_SLEEP = 10  # [초기값] KillSwitch 대기
_LEVERAGE = 20  # [검증값]
_START_EQUITY = 700.0  # [검증값]
_TARGET_EQUITY = 10000.0  # [검증값]
_PAPER_MAKER_FEE_RATE = 0.0002  # [검증값] Paper mode 청산 수수료 Limit 0.02%


def _get_atr_from_state(market_state: Dict[str, Any]) -> float:
    """market_state에서 ATR 계산."""
    klines = market_state.get("klines_3m") or []
    if len(klines) < 15:
        return 0.0
    highs = [float(k.get("high", 0)) for k in klines]
    lows = [float(k.get("low", 0)) for k in klines]
    closes = [float(k.get("close", 0)) for k in klines]
    atrs = compute_atr(highs, lows, closes, 14)
    return atrs[-1] if atrs else 0.0


def _get_funding_direction_bias(funding_rate: float) -> Optional[str]:
    """funding rate 기반 방향 편향."""
    if funding_rate >= 0.001:  # [초기값]
        return "SHORT"
    if funding_rate <= -0.0005:  # [초기값]
        return "LONG"
    return None


class TradingLoop:
    """
    전체 시스템 23단계 이벤트 루프.
    paper_mode=True → 실제 주문 없음.
    """

    def __init__(self, paper_mode: bool = True, http_client: Any = None) -> None:
        self._paper_mode = paper_mode
        cfg_obj = ConfigManager()
        _ = cfg_obj.load_system_config()
        cfg = cfg_obj

        self._state_store = StateStore()
        self._mdm = MarketDataManager(cfg_obj.get_config())
        # ── 동적 심볼 선정 ─────────────────────────────────────────
        _scan_symbols_cfg = str(cfg.get("scan_symbols", "")).strip()
        _top_n = int(cfg.get("scan_top_n_by_volume", 20))       # [초기값]
        _min_vol = float(cfg.get("scan_min_volume_usd", 100_000_000.0))  # [초기값]
        _fallback_raw = str(cfg.get("scan_symbol_fallback", "BTCUSDT,ETHUSDT,SOLUSDT"))
        _fallback = [s.strip() for s in _fallback_raw.split(",") if s.strip()]

        if _scan_symbols_cfg:
            # 고정 심볼 모드 (scan_symbols 에 값이 있는 경우)
            _scan_symbols = [s.strip() for s in _scan_symbols_cfg.split(",") if s.strip()]
            logger.info("trading_loop MDM fixed symbols=%s", _scan_symbols)
        else:
            # 동적 스캔 모드 — 거래량 상위 N개 자동 선정
            _scan_symbols = self._mdm.get_top_symbols_by_volume(
                top_n=_top_n, min_volume_usd=_min_vol
            )
            if not _scan_symbols:
                _scan_symbols = _fallback
                logger.warning(
                    "trading_loop dynamic symbol fetch failed — using fallback=%s",
                    _fallback,
                )
            logger.info(
                "trading_loop MDM dynamic symbols top%d min_vol=$%.0fM symbols=%s",
                _top_n, _min_vol / 1e6, _scan_symbols,
            )

        self._mdm.initialize(_scan_symbols)
        logger.info(
            "trading_loop MDM initialized symbols=%s",
            _scan_symbols,
        )
        self._session_filter = SessionFilter()
        self._macro_filter = MacroMarketFilter()
        self._coin_scanner = AICoinScanner()
        self._regime_engine = MarketRegimeEngine()
        self._orderflow_engine = OrderflowEngine()
        self._cost_guard = ExecutionCostGuard()

        weights = StrategyWeights()
        self._feedback = StrategyFeedback(weights)
        self._selector = RuleBasedSelector(weights=weights)
        self._entry_score = EntryScoreEngine()
        self._position_scaler = PositionScaler()
        self._growth_engine = AccountGrowthEngine()
        self._risk_engine = RiskEngine()
        self._drawdown_mgr = DrawdownManager()
        self._exec_engine = ExecutionEngine(paper_mode=paper_mode, http_client=http_client)
        self._order_router = OrderRouter(paper_mode=paper_mode)
        self._analytics = AnalyticsEngine()
        self._target_tracker = TargetTracker()

        # FIX 7: 디스크에서 이전 상태 복원 (equity, peak_equity)
        self._state_store.load_from_disk()
        _saved_equity = self._state_store.get("equity",      _START_EQUITY)
        _saved_peak   = self._state_store.get("peak_equity", _START_EQUITY)
        if _saved_peak > 0:
            self._drawdown_mgr.peak_equity    = _saved_peak
            self._drawdown_mgr.current_equity = _saved_equity
        logger.info(
            "trading_loop state_restored equity=%.2f peak_equity=%.2f",
            _saved_equity, _saved_peak,
        )

        # FIX 2: analytics 거래 수를 state_store에 동기화 (cold_start 판정 정확화)
        _loaded_count = self._analytics.get_total_trade_count()
        self._state_store.update("total_trade_count", _loaded_count)
        logger.info(
            "trading_loop total_trade_count synced count=%d", _loaded_count
        )

        from src.utils.config_loader import load_strategy_config

        from src.strategy.strategy_library.vwap_pullback import VWAPPullback
        from src.strategy.strategy_library.trend_continuation import TrendContinuation
        from src.strategy.strategy_library.liquidity_sweep_reversal import (
            LiquiditySweepReversal,
        )
        from src.strategy.strategy_library.breakout_momentum import BreakoutMomentum
        from src.strategy.strategy_library.liquidation_scalping import LiquidationScalping
        from src.strategy.strategy_library.stop_hunt_reversal import StopHuntReversal
        from src.strategy.strategy_library.ema_cross_scalping import EMACrossScalping

        scfg = load_strategy_config()
        self._strategy_lib = {
            "vwap_pullback": VWAPPullback(scfg["vwap_pullback"]),
            "trend_continuation": TrendContinuation(scfg["trend_continuation"]),
            "liquidity_sweep_reversal": LiquiditySweepReversal(
                scfg["liquidity_sweep_reversal"]
            ),
            "breakout_momentum": BreakoutMomentum(scfg["breakout_momentum"]),
            "liquidation_scalping": LiquidationScalping(scfg["liquidation_scalping"]),
            "stop_hunt_reversal": StopHuntReversal(scfg["stop_hunt_reversal"]),
            "ema_cross_scalping": EMACrossScalping(scfg["ema_cross_scalping"]),
        }

        self._elapsed_days = 0.0
        self._start_time = time.time()
        self._last_reset_date: str = ""  # [FIX 14] 일일 리셋 중복 방지

    def run(self) -> None:
        """메인 루프. 예외 발생 시 1초 대기 후 재시도."""
        logger.info("trading_loop START paper_mode=%s", self._paper_mode)
        while True:
            try:
                self._execute_loop()
            except Exception as exc:
                logger.error("trading_loop loop_error error=%s", exc)
                time.sleep(1)

    def run_once(self) -> Dict[str, Any]:
        """루프 1회 실행 (테스트용). 결과 dict 반환."""
        try:
            return self._execute_loop_result()
        except Exception as exc:
            logger.error("trading_loop run_once failed error=%s", exc)
            return {"status": "ERROR", "reason": str(exc)}

    def _execute_loop(self) -> None:
        self._execute_loop_result()
        time.sleep(_LOOP_SLEEP_SEC)

    def _execute_loop_result(self) -> Dict[str, Any]:
        """23단계 실행. 결과 dict 반환 (테스트 호환)."""
        now = datetime.now(timezone.utc)
        _today_str = now.strftime("%Y-%m-%d")
        if (
            now.hour == 0
            and now.minute == 0
            and self._last_reset_date != _today_str
        ):
            self._growth_engine.reset_daily()
            self._risk_engine.reset_daily()
            self._state_store.reset_daily()
            self._last_reset_date = _today_str
            logger.info("trading_loop daily_reset date=%s", _today_str)
        self._elapsed_days = (time.time() - self._start_time) / 86400

        try:
            # 1. Market Data 갱신
            self._mdm.refresh_all()
        except Exception as exc:
            logger.error("step1 mdm refresh failed error=%s", exc)

        # 1-B. Paper mode 포지션 청산 체크 (최신 가격 기준) [FIX 4]
        self._check_paper_positions()

        # 2. Session Filter
        session_result = self._session_filter.check(now)
        if not session_result.get("allowed", False):  # [FIX 13]
            _equity_now = self._state_store.get("equity", 700.0)
            _macro_now = self._state_store.get("macro_state", "NEUTRAL")
            return {
                "status": "SESSION_CLOSED",
                "equity": _equity_now,
                "macro_state": _macro_now,
                "session": session_result,
            }
        # 3. Kill Switch 확인
        if self._risk_engine.kill_switch.is_blocked():
            _equity_now = self._state_store.get("equity", 700.0)
            _macro_now = self._state_store.get("macro_state", "NEUTRAL")
            return {"status": "KILL_SWITCH_ACTIVE", "equity": _equity_now, "macro_state": _macro_now}

        # 4. 계좌 잔고 갱신
        equity = self._get_equity()
        self._state_store.update("equity", equity)
        self._drawdown_mgr.update_equity(equity)
        daily_pnl = self._state_store.get("daily_pnl", 0.0)
        growth_params = self._growth_engine.get_trade_parameters(equity, daily_pnl)
        effective_score_min = max(
            self._session_filter.get_effective_entry_score_min(now),
            growth_params.get("min_entry_score", 70),
        )

        if growth_params["is_halted"]:
            return {
                "status": "PROFIT_LOCK_HALTED",
                "equity": equity,
                "macro_state": self._state_store.get("macro_state", "NEUTRAL"),
            }

        # 5. Coin Scanner (60초 주기)
        if time.time() - self._state_store.get("last_scan_time", 0.0) > _SCAN_INTERVAL:
            btc_state = self._mdm.get_state("BTCUSDT") or {}
            macro_state = self._macro_filter.get_state(btc_state)
            self._coin_scanner.set_macro_state(macro_state)
            top3 = self._coin_scanner.scan(mdm=self._mdm)
            self._state_store.update("macro_state", macro_state)
            self._state_store.update("top3", top3)
            self._state_store.update("last_scan_time", time.time())

        macro_state = self._state_store.get("macro_state", "NEUTRAL")
        top3 = self._state_store.get("top3", [])

        if macro_state == "RISK_OFF" or not top3:
            return {
                "status": "RISK_OFF_OR_NO_TOP3",
                "equity": equity,
                "macro_state": macro_state,
            }

        # 6~23. TOP3 코인별 루프
        trades_executed: List[Dict[str, Any]] = []
        for coin in top3:
            result = self._process_coin(
                coin,
                macro_state,
                growth_params,
                effective_score_min,
                now,
            )
            if result.get("traded"):
                trades_executed.append(result)
                break

        self._state_store.update("drawdown_state", self._drawdown_mgr.get_state())
        self._state_store.update(
            "kill_switch_active", self._risk_engine.kill_switch.is_active
        )

        return {
            "status": "OK",
            "macro_state": macro_state,
            "equity": equity,
            "trades_executed": len(trades_executed),
            "growth_params": growth_params,
        }

    def _process_coin(
        self,
        coin: Dict[str, Any],
        macro_state: str,
        growth_params: Dict[str, Any],
        effective_score_min: int,
        now: datetime,
    ) -> Dict[str, Any]:
        """단계 6~23: 단일 코인 처리."""
        symbol = coin.get("symbol", "BTCUSDT")
        open_pos = self._state_store.get("open_positions", {})
        if symbol in open_pos:
            return {"traded": False, "reason": "ALREADY_OPEN"}
        coin_type = coin.get("coin_type", "CORE")
        grade = coin.get("grade", "B")

        if self._risk_engine.kill_switch.is_symbol_blocked(symbol):
            return {"traded": False, "reason": "SYMBOL_BLOCKED"}
        daily_pnl = self._state_store.get("daily_pnl", 0.0)
        stage = self._growth_engine._stage_mgr.get_current_stage(
            self._state_store.get("equity", _START_EQUITY)
        )
        market_state_for_risk = self._mdm.get_state(symbol) or {}
        pre_ok, pre_reason = self._risk_engine.check_pre_trade(
            symbol, "", daily_pnl, stage, market_state_for_risk
        )
        if not pre_ok:
            return {"traded": False, "reason": pre_reason}

        market_state = self._mdm.get_state(symbol) or {}

        # 7. Regime 판정
        regime = self._regime_engine.get_regime(symbol, market_state)
        if self._risk_engine.kill_switch.is_regime_blocked(regime):
            return {"traded": False, "reason": "REGIME_BLOCKED"}

        # 8. Orderflow
        orderflow_state = self._orderflow_engine.compute(symbol, market_state)

        # 9~10. Funding & Direction
        funding_rate = float(market_state.get("funding_rate", 0.0))
        direction_bias = _get_funding_direction_bias(funding_rate)

        # 11. 전략 후보
        total_count = self._state_store.get("total_trade_count", 0)
        candidates = self._selector.select(
            symbol,
            macro_state,
            regime,
            coin_type,
            effective_score_min,
            total_count,
        )
        if not candidates:
            logger.info(
                "process_coin NO_CANDIDATES symbol=%s macro=%s regime=%s "
                "coin_type=%s score_min=%d",
                symbol,
                macro_state,
                regime,
                coin_type,
                effective_score_min,
            )
            return {"traded": False, "reason": "NO_CANDIDATES"}

        # 12~23. 전략별 신호 → 실행
        for strategy_name in candidates:
            strategy = self._strategy_lib.get(strategy_name)
            if not strategy:
                continue
            if not strategy.is_allowed(macro_state, regime):
                logger.info(
                    "process_coin NOT_ALLOWED symbol=%s strategy=%s "
                    "macro=%s regime=%s allowed=%s forbidden=%s",
                    symbol,
                    strategy_name,
                    macro_state,
                    regime,
                    strategy.config.get("allowed_regimes", []),
                    strategy.config.get("forbidden_regimes", []),
                )
                continue

            # 13. Signal
            signal, layer_hit = strategy.generate_signal(
                symbol, market_state, orderflow_state, direction_bias
            )
            if not signal:
                logger.info(
                    "process_coin NO_SIGNAL symbol=%s strategy=%s "
                    "l1=%s l2=%s l3=%s direction=%s",
                    symbol,
                    strategy_name,
                    layer_hit.get("layer1"),
                    layer_hit.get("layer2"),
                    layer_hit.get("layer3"),
                    layer_hit.get("direction"),
                )
                continue

            direction = layer_hit.get("direction") or "LONG"
            logger.info(
                "process_coin SIGNAL_TRUE symbol=%s strategy=%s "
                "direction=%s regime=%s macro=%s",
                symbol,
                strategy_name,
                direction,
                regime,
                macro_state,
            )

            # 14. Entry Score
            score_result = self._entry_score.compute(
                symbol,
                strategy_name,
                direction,
                regime,
                grade,
                market_state,
                orderflow_state,
                layer_hit,
                funding_rate,
            )
            _c = score_result.get("components", {})
            logger.info(
                "process_coin ENTRY_SCORE symbol=%s strategy=%s dir=%s "
                "score=%.1f min=%d scale=%.1f quality=%s | "
                "trend=%.1f vwap=%.1f regime=%.1f scanner=%.1f "
                "vol=%.1f vola=%.1f of=%.1f pattern=%.1f funding=%.1f",
                symbol,
                strategy_name,
                direction,
                score_result["total_score"],
                effective_score_min,
                score_result["position_scale"],
                score_result.get("entry_quality", "?"),
                _c.get("trend", 0),
                _c.get("vwap", 0),
                _c.get("regime", 0),
                _c.get("scanner", 0),
                _c.get("volume", 0),
                _c.get("volatility", 0),
                _c.get("orderflow", 0),
                _c.get("pattern", 0),
                _c.get("funding", 0),
            )
            if score_result["total_score"] < effective_score_min:
                logger.info(
                    "process_coin BLOCKED_SCORE symbol=%s score=%.1f < min=%d",
                    symbol,
                    score_result["total_score"],
                    effective_score_min,
                )
                continue
            if score_result["position_scale"] == 0.0:
                logger.info(
                    "process_coin BLOCKED_SCALE symbol=%s score=%.1f quality=%s",
                    symbol,
                    score_result["total_score"],
                    score_result.get("entry_quality", "?"),
                )
                continue

            # 15. RR 검사
            atr = _get_atr_from_state(market_state)
            if atr <= 0:
                continue
            entry_price = float(market_state.get("last_price", 0))
            if entry_price <= 0:
                continue
            stop_price = self._position_scaler.compute_stop_price(
                entry_price, atr, regime, direction
            )
            tp1_price, tp2_price = self._position_scaler.compute_tp_prices(
                entry_price, atr, regime, direction
            )
            rr_ok, rr_val = strategy.validate_rr(entry_price, stop_price, tp1_price)
            _min_rr = strategy.config.get("min_rr", 1.2)
            logger.info(
                "process_coin RR symbol=%s strategy=%s "
                "entry=%.5f stop=%.5f tp1=%.5f atr=%.5f "
                "rr=%.3f min_rr=%.1f ok=%s",
                symbol,
                strategy_name,
                entry_price,
                stop_price,
                tp1_price,
                atr,
                rr_val,
                _min_rr,
                rr_ok,
            )
            if not rr_ok:
                logger.info(
                    "process_coin BLOCKED_RR symbol=%s rr=%.3f < min_rr=%.1f",
                    symbol,
                    rr_val,
                    _min_rr,
                )
                continue

            # 16. Cost Guard
            order_type = self._order_router.decide_order_type(
                symbol, market_state
            )
            if order_type == "HOLD":
                continue
            equity = self._state_store.get("equity", _START_EQUITY)
            # FIX 18: preliminary position size 기반 actual_notional 계산
            _prelim_size = self._position_scaler.compute_position_size(
                equity,
                growth_params["risk_pct"],
                atr,
                regime,
                _LEVERAGE,
                entry_price,
            )
            order_size_usd = (
                _prelim_size * entry_price
                if _prelim_size > 0
                else equity * growth_params["risk_pct"] * _LEVERAGE
            )
            cost_ok, cost_detail = self._cost_guard.check(
                symbol,
                order_type,
                order_size_usd,
                tp1_price,
                entry_price,
                regime,
                now,
                funding_rate,
                int(score_result["total_score"]),
                market_state,
            )
            logger.info(
                "process_coin COST_GUARD symbol=%s order_type=%s "
                "size_usd=%.2f ok=%s detail=%s",
                symbol,
                order_type,
                order_size_usd,
                cost_ok,
                cost_detail,
            )
            if not cost_ok:
                logger.info(
                    "process_coin BLOCKED_COST symbol=%s detail=%s",
                    symbol,
                    cost_detail,
                )
                continue

            # 17. Drawdown 조정
            dd_adj = self._drawdown_mgr.get_risk_adjustment()
            risk_pct = growth_params["risk_pct"] * dd_adj["risk_multiplier"]
            if risk_pct <= 0:
                continue

            # 18. 포지션 사이즈
            pos_size = self._position_scaler.compute_position_size(
                equity,
                risk_pct,
                atr,
                regime,
                _LEVERAGE,
            )
            pos_size *= score_result["position_scale"]
            pos_size *= growth_params["scale_limit"]
            pos_size = round(pos_size, 3)
            logger.info(
                "process_coin POS_SIZE symbol=%s "
                "equity=%.2f risk_pct=%.5f dd_mult=%.2f "
                "atr=%.5f leverage=%d pos_size=%.4f",
                symbol,
                equity,
                risk_pct,
                dd_adj["risk_multiplier"],
                atr,
                _LEVERAGE,
                pos_size,
            )
            if pos_size <= 0:
                logger.info(
                    "process_coin BLOCKED_POS_SIZE symbol=%s size=%.4f",
                    symbol,
                    pos_size,
                )
                continue

            # 19. 주문 실행
            tp1_ratio = self._position_scaler.get_tp1_ratio(regime)
            logger.info(
                "process_coin EXECUTING symbol=%s strategy=%s dir=%s "
                "entry=%.5f stop=%.5f tp1=%.5f pos=%.4f score=%.1f",
                symbol,
                strategy_name,
                direction,
                entry_price,
                stop_price,
                tp1_price,
                pos_size,
                score_result["total_score"],
            )
            exec_result = self._exec_engine.execute(
                symbol,
                direction,
                1.0,
                pos_size,
                entry_price,
                stop_price,
                tp1_price,
                tp2_price,
                tp1_ratio,
                regime,
                market_state,
            )
            if exec_result.get("blocked"):
                continue

            # 20. SL 등록 확인
            if not exec_result.get("sl_registered", True):
                self._risk_engine.kill_switch.trigger("STOP_NOT_REGISTERED")
                continue

            # 22. 거래 기록
            trade_record = {
                "timestamp": now.isoformat(),
                "symbol": symbol,
                "coin_type": coin_type,
                "strategy": strategy_name,
                "regime": regime,
                "macro_state": macro_state,
                "scanner_grade": grade,
                "direction": direction,
                "entry_score": score_result["total_score"],
                "position_scale": score_result["position_scale"],
                "funding_rate": funding_rate,
                "order_type": exec_result.get("order_type", ""),
                "fee_usd": exec_result.get("fee_usd", 0.0),
                "pnl_net": 0.0,  # paper_mode: 미실현 손익 0 (fee는 별도 기록)
                "r_multiple": 0.0,
                "sl_registered": exec_result.get("sl_registered", True),
                "strategy_layer_hit": layer_hit,
                "drawdown_state": self._drawdown_mgr.get_state(),
                "entry_score_components": score_result.get("components", {}),
            }
            self._analytics.record_trade(trade_record)
            open_pos = self._state_store.get("open_positions", {})
            open_pos[symbol] = {"direction": direction, "entry_price": entry_price}
            self._state_store.update("open_positions", open_pos)

            # 23. 상태 업데이트
            pnl = trade_record.get("pnl_net", 0.0)
            self._state_store.update(
                "daily_pnl", self._state_store.get("daily_pnl", 0.0) + pnl
            )
            self._state_store.update(
                "total_trade_count", self._state_store.get("total_trade_count", 0) + 1
            )
            self._growth_engine.update_daily_pnl(pnl)
            self._feedback.record(strategy_name, symbol, regime, pnl, 0.0)
            self._risk_engine.check_post_trade(symbol, regime, pnl, 0.0)

            return {
                "traded": True,
                "symbol": symbol,
                "strategy": strategy_name,
                "exec": exec_result,
            }

        return {"traded": False, "reason": "NO_SIGNAL"}

    def _get_equity(self) -> float:
        """paper_mode → state_store 잔고 반환. 실거래 → API 호출."""
        if self._paper_mode:
            return float(self._state_store.get("equity", _START_EQUITY))
        try:
            return float(self._state_store.get("equity", _START_EQUITY))
        except Exception:
            return _START_EQUITY

