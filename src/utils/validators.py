from __future__ import annotations

import math
from typing import Any, Iterable, Mapping


class ValidationError(Exception):
    """설정 검증 관련 예외."""


def validate_required_keys(
    config: Mapping[str, object], required_keys: Iterable[str]
) -> None:
    missing = [k for k in required_keys if k not in config]
    if missing:
        raise ValidationError(f"Missing required config keys: {', '.join(missing)}")


def validate_numeric_keys(
    config: Mapping[str, object], numeric_keys: Iterable[str]
) -> None:
    invalid: list[str] = []
    for key in numeric_keys:
        value = config.get(key)
        if not isinstance(value, (int, float)):
            invalid.append(key)
    if invalid:
        raise ValidationError(
            f"Non-numeric config values for keys: {', '.join(invalid)}"
        )


def validate_modes(paper_mode: bool, live_mode: bool) -> None:
    if paper_mode and live_mode:
        raise ValidationError("paper_mode and live_mode cannot both be true")


def validate_config(config: Mapping[str, Any]) -> bool:
    """
    system_config 전체 유효성 검사.
    타입/범위/논리 검사. 실패 시 ValidationError. 성공 시 True.
    """
    paper = config.get("paper_mode")
    live  = config.get("live_mode")
    if paper is True and live is True:
        raise ValidationError("paper_mode and live_mode cannot both be true")

    _assert_type(config, "capital_start",   (int, float))
    _assert_type(config, "capital_target",  (int, float))
    _assert_type(config, "leverage",        (int, float))
    _assert_type(config, "paper_mode",      bool)
    _assert_type(config, "live_mode",       bool)
    _assert_type(config, "entry_score_min", (int, float))
    _assert_type(config, "trade_sessions",  list)

    leverage = float(config.get("leverage", 1))
    if not (1 <= leverage <= 125):
        raise ValidationError(f"leverage must be 1~125, got {leverage}")

    capital_start = float(config.get("capital_start", 0))
    if capital_start <= 0:
        raise ValidationError(f"capital_start must be > 0, got {capital_start}")

    entry_score_min = float(config.get("entry_score_min", 0))
    if not (0 <= entry_score_min <= 100):
        raise ValidationError(
            f"entry_score_min must be 0~100, got {entry_score_min}"
        )

    max_capital_usage = config.get("max_capital_usage")
    if max_capital_usage is not None:
        if not (0 < float(max_capital_usage) <= 1):
            raise ValidationError(
                f"max_capital_usage must be 0~1, got {max_capital_usage}"
            )

    return True


def validate_order_params(params: Mapping[str, Any]) -> bool:
    """
    주문 파라미터 유효성 검사.
    symbol, side, qty, price + qty precision 검사.
    실패 시 ValidationError. 성공 시 True.
    """
    required = ["symbol", "side", "qty", "price"]
    missing = [k for k in required if k not in params]
    if missing:
        raise ValidationError(f"Missing order params: {', '.join(missing)}")

    symbol = params["symbol"]
    if not isinstance(symbol, str) or not symbol.strip():
        raise ValidationError(
            f"symbol must be a non-empty string, got {symbol!r}"
        )

    side = params["side"]
    if side not in ("Buy", "Sell"):
        raise ValidationError(f"side must be 'Buy' or 'Sell', got {side!r}")

    qty = params["qty"]
    if not isinstance(qty, (int, float)):
        raise ValidationError(f"qty must be numeric, got {type(qty)}")
    if not math.isfinite(float(qty)) or float(qty) <= 0:
        raise ValidationError(f"qty must be finite and > 0, got {qty}")

    price = params["price"]
    if not isinstance(price, (int, float)):
        raise ValidationError(f"price must be numeric, got {type(price)}")
    if not math.isfinite(float(price)) or float(price) <= 0:
        raise ValidationError(f"price must be finite and > 0, got {price}")

    return True


def _assert_type(config: Mapping[str, Any], key: str, expected: Any) -> None:
    val = config.get(key)
    if val is None:
        return
    if not isinstance(val, expected):
        raise ValidationError(
            f"Config key '{key}' expected type {expected}, "
            f"got {type(val).__name__}"
        )

