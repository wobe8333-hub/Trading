from src.app.config_loader import get_config
from src.core.market_data.market_data_manager import MarketDataManager


def test_market_data_layer_smoke() -> None:
    config = get_config()
    manager = MarketDataManager(config)
    manager.initialize(["BTCUSDT", "ETHUSDT", "SOLUSDT"])
    manager.start()

    btc_state = manager.get_market_state("BTCUSDT")
    eth_state = manager.get_market_state("ETHUSDT")
    sol_state = manager.get_market_state("SOLUSDT")

    assert btc_state is not None
    assert eth_state is not None
    assert sol_state is not None

    health = manager.healthcheck()
    assert health["tracked_symbol_count"] == 3
    assert health["metadata_count"] >= 3
    assert health["symbols_ready"] is True
    assert health["degraded"] is False

