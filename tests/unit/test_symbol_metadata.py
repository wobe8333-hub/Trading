from src.core.market_data.symbol_metadata import SymbolMetadata, SymbolMetadataStore


def test_metadata_set_get_and_has_and_clear() -> None:
    store = SymbolMetadataStore()

    meta = SymbolMetadata(
        symbol="BTCUSDT",
        tick_size=0.1,
        qty_step=0.001,
        min_order_qty=0.001,
        min_notional=10.0,
        price_scale=1,
        base_coin="BTC",
        quote_coin="USDT",
        status="Trading",
        updated_ts_ms=123456789,
    )

    store.set(meta)
    assert store.has("BTCUSDT")

    got = store.get("BTCUSDT")
    assert got is not None
    assert got.symbol == "BTCUSDT"

    # bulk_set
    store.bulk_set(
        {
            "ETHUSDT": {
                "tick_size": 0.01,
                "qty_step": 0.001,
                "min_order_qty": 0.001,
                "min_notional": 10.0,
                "price_scale": 2,
                "base_coin": "ETH",
                "quote_coin": "USDT",
            }
        }
    )
    assert store.has("ETHUSDT")

    as_dict = store.to_dict()
    assert "BTCUSDT" in as_dict
    assert "ETHUSDT" in as_dict

    store.clear()
    assert not store.has("BTCUSDT")
    assert store.to_dict() == {}

