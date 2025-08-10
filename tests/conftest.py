"""Pytest configuration and shared fixtures for tests."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock

import polars as pl
import pytest
from project_x_py import TradingSuite


@pytest.fixture
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def mock_suite():
    """Create a mock TradingSuite for testing."""
    suite = MagicMock(spec=TradingSuite)

    # Mock data manager
    suite.data = AsyncMock()
    suite.data.get_data = AsyncMock()
    suite.data.get_current_price = AsyncMock(return_value=5000.0)

    # Mock orderbook
    suite.orderbook = AsyncMock()
    suite.orderbook.get_market_imbalance = AsyncMock()
    suite.orderbook.detect_iceberg_orders = AsyncMock(return_value={"iceberg_levels": []})
    suite.orderbook.get_orderbook_snapshot = AsyncMock()

    # Mock orders
    suite.orders = AsyncMock()
    suite.orders.place_bracket_order = AsyncMock(return_value="ORDER123")
    suite.orders.modify_order = AsyncMock()
    suite.orders.close_position = AsyncMock()

    # Mock client
    suite.client = Mock()
    account_info = Mock()
    account_info.balance = 100000
    account_info.margin = 50000
    suite.client.get_account_info = Mock(return_value=account_info)

    # Mock instrument
    suite.instrument = Mock()
    suite.instrument.id = "ES"
    suite.instrument.tickSize = 0.25
    suite.instrument.tickValue = 12.50

    return suite


@pytest.fixture
def sample_ohlcv_data():
    """Create sample OHLCV data for testing."""
    timestamps = pl.datetime_range(
        start=pl.datetime(2024, 1, 1, 9, 30),
        end=pl.datetime(2024, 1, 1, 9, 35),
        interval="15s",
        eager=True
    )
    n = len(timestamps)
    return pl.DataFrame({
        "timestamp": timestamps,
        "open": [5000.0 + i * 0.5 for i in range(n)],
        "high": [5002.0 + i * 0.5 for i in range(n)],
        "low": [4999.0 + i * 0.5 for i in range(n)],
        "close": [5001.0 + i * 0.5 for i in range(n)],
        "volume": [100 + i * 10 for i in range(n)]
    })


@pytest.fixture
def sample_1min_data():
    """Create sample 1-minute OHLCV data for testing."""
    return pl.DataFrame({
        "timestamp": pl.datetime_range(
            start=pl.datetime(2024, 1, 1, 9, 0),
            end=pl.datetime(2024, 1, 1, 9, 20),
            interval="1m",
            eager=True
        ),
        "open": [5000.0 + i for i in range(21)],
        "high": [5002.0 + i for i in range(21)],
        "low": [4999.0 + i for i in range(21)],
        "close": [5001.0 + i for i in range(21)],
        "volume": [100 + i * 10 for i in range(21)]
    })


@pytest.fixture
def sample_5min_data():
    """Create sample 5-minute OHLCV data for testing."""
    return pl.DataFrame({
        "timestamp": pl.datetime_range(
            start=pl.datetime(2024, 1, 1, 8, 0),
            end=pl.datetime(2024, 1, 1, 10, 0),
            interval="5m",
            eager=True
        ),
        "open": [5000.0 + i * 2 for i in range(25)],
        "high": [5003.0 + i * 2 for i in range(25)],
        "low": [4998.0 + i * 2 for i in range(25)],
        "close": [5001.0 + i * 2 for i in range(25)],
        "volume": [500 + i * 50 for i in range(25)]
    })


@pytest.fixture
def sample_15min_data():
    """Create sample 15-minute OHLCV data for testing."""
    return pl.DataFrame({
        "timestamp": pl.datetime_range(
            start=pl.datetime(2024, 1, 1, 6, 0),
            end=pl.datetime(2024, 1, 1, 12, 0),
            interval="15m",
            eager=True
        ),
        "open": [5000.0 + i * 5 for i in range(25)],
        "high": [5005.0 + i * 5 for i in range(25)],
        "low": [4995.0 + i * 5 for i in range(25)],
        "close": [5002.0 + i * 5 for i in range(25)],
        "volume": [1000 + i * 100 for i in range(25)]
    })


@pytest.fixture
def bullish_trend_data():
    """Create data representing a bullish trend."""
    return pl.DataFrame({
        "timestamp": pl.datetime_range(
            start=pl.datetime(2024, 1, 1, 9, 0),
            end=pl.datetime(2024, 1, 1, 9, 30),
            interval="15s",
            eager=True
        ),
        "open": [5000.0 + i * 0.5 for i in range(121)],
        "high": [5001.0 + i * 0.5 for i in range(121)],
        "low": [4999.5 + i * 0.5 for i in range(121)],
        "close": [5000.5 + i * 0.5 for i in range(121)],
        "volume": [100 + i for i in range(121)]
    })


@pytest.fixture
def bearish_trend_data():
    """Create data representing a bearish trend."""
    return pl.DataFrame({
        "timestamp": pl.datetime_range(
            start=pl.datetime(2024, 1, 1, 9, 0),
            end=pl.datetime(2024, 1, 1, 9, 30),
            interval="15s",
            eager=True
        ),
        "open": [5100.0 - i * 0.5 for i in range(121)],
        "high": [5101.0 - i * 0.5 for i in range(121)],
        "low": [5099.5 - i * 0.5 for i in range(121)],
        "close": [5099.5 - i * 0.5 for i in range(121)],
        "volume": [100 + i for i in range(121)]
    })
