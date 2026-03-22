from src.app.config_loader import Config, get_config
from src.utils.config_loader import (
    ConfigManager,
    get_stage_for_equity,
    load_stage_config,
    load_strategy_config,
    load_system_config,
)
from src.utils.validators import (
    ValidationError,
    validate_config,
    validate_order_params,
)


# ── Config 싱글톤 ───────────────────────────────────────────────

def test_config_singleton_and_values() -> None:
    cfg1: Config = get_config()
    cfg2: Config = get_config()
    assert cfg1 is cfg2
    assert cfg1.paper_mode is True
    assert cfg1.live_mode is False
    assert cfg1.risk_stage == "Stage1"
    assert cfg1.capital_start == 700
    assert cfg1.entry_score_high_risk_min == 80


# ── ConfigManager ───────────────────────────────────────────────

def test_config_manager_get_capital_start() -> None:
    ConfigManager._instance = None
    ConfigManager._cache    = None
    c = ConfigManager()
    assert c.get("capital_start") == 700


def test_config_manager_singleton() -> None:
    c1 = ConfigManager()
    c2 = ConfigManager()
    assert c1 is c2


def test_config_manager_reload() -> None:
    c = ConfigManager()
    c.reload()
    assert c.get("capital_start") == 700


# ── load_stage_config / get_stage_for_equity ───────────────────

def test_load_stage_config_returns_list() -> None:
    stages = load_stage_config()
    assert isinstance(stages, list)
    assert len(stages) == 4


def test_stage_config_has_required_fields() -> None:
    stages = load_stage_config()
    for s in stages:
        assert "id"                 in s
        assert "equity_min"         in s
        assert "equity_max"         in s
        assert "risk_pct_per_trade" in s
        assert "daily_loss_limit"   in s
        assert "profit_locks"       in s


def test_get_stage_for_equity_700() -> None:
    stage = get_stage_for_equity(700)
    assert stage["id"] == 1


def test_get_stage_for_equity_1500() -> None:
    stage = get_stage_for_equity(1500)
    assert stage["id"] == 2


def test_get_stage_for_equity_3000() -> None:
    stage = get_stage_for_equity(3000)
    assert stage["id"] == 3


def test_get_stage_for_equity_6000() -> None:
    stage = get_stage_for_equity(6000)
    assert stage["id"] == 4


# ── load_strategy_config ────────────────────────────────────────

def test_load_strategy_config_has_7_strategies() -> None:
    strategies = load_strategy_config()
    assert isinstance(strategies, dict)
    assert len(strategies) == 7


def test_strategy_names() -> None:
    strategies = load_strategy_config()
    expected = {
        "vwap_pullback",
        "trend_continuation",
        "liquidity_sweep_reversal",
        "breakout_momentum",
        "liquidation_scalping",
        "stop_hunt_reversal",
        "ema_cross_scalping",
    }
    assert set(strategies.keys()) == expected


# ── validate_config ─────────────────────────────────────────────

def test_validate_config_pass() -> None:
    cfg = {
        "capital_start": 700,
        "capital_target": 10000,
        "leverage": 20,
        "paper_mode": True,
        "live_mode": False,
        "entry_score_min": 70,
        "trade_sessions": ["SEOUL"],
        "bybit_api_key": "",
        "bybit_api_secret": "",
        "max_capital_usage": 0.25,
    }
    assert validate_config(cfg) is True


def test_validate_config_both_modes_fail() -> None:
    cfg = {"paper_mode": True, "live_mode": True}
    try:
        validate_config(cfg)
        assert False, "ValidationError not raised"
    except (Exception,) as e:
        assert "cannot both be true" in str(e)


def test_validate_config_leverage_out_of_range() -> None:
    cfg = {
        "capital_start": 700, "capital_target": 10000,
        "leverage": 200, "paper_mode": True, "live_mode": False,
        "entry_score_min": 70, "trade_sessions": [],
    }
    try:
        validate_config(cfg)
        assert False, "ValidationError not raised"
    except (Exception,) as e:
        assert "leverage" in str(e)


# ── validate_order_params ───────────────────────────────────────

def test_validate_order_params_pass() -> None:
    params = {"symbol": "BTCUSDT", "side": "Buy", "qty": 0.001, "price": 65000.0}
    assert validate_order_params(params) is True


def test_validate_order_params_invalid_side() -> None:
    params = {"symbol": "BTCUSDT", "side": "LONG", "qty": 0.001, "price": 65000.0}
    try:
        validate_order_params(params)
        assert False, "ValidationError not raised"
    except (Exception,) as e:
        assert "side" in str(e)


def test_validate_order_params_zero_qty() -> None:
    params = {"symbol": "BTCUSDT", "side": "Buy", "qty": 0, "price": 65000.0}
    try:
        validate_order_params(params)
        assert False, "ValidationError not raised"
    except (Exception,) as e:
        assert "qty" in str(e)

from src.app.config_loader import Config, get_config


def test_config_singleton_and_values() -> None:
    cfg1: Config = get_config()
    cfg2: Config = get_config()

    assert cfg1 is cfg2
    assert cfg1.paper_mode is True
    assert cfg1.live_mode is False

    # capital_start=700이면 Stage1이어야 한다.
    assert cfg1.risk_stage == "Stage1"

