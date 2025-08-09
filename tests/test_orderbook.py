"""Unit tests for the orderbook module."""

from unittest.mock import Mock

import pytest

from strategy.orderbook import OrderBookAnalyzer


class TestOrderBookAnalyzer:
    """Test suite for OrderBookAnalyzer class."""

    @pytest.mark.asyncio
    async def test_initialization(self, mock_suite):
        """Test OrderBookAnalyzer initialization."""
        analyzer = OrderBookAnalyzer(mock_suite)
        assert analyzer.suite == mock_suite
        assert analyzer.imbalance_long_threshold == 1.5
        assert analyzer.imbalance_short_threshold == 0.6667
        assert analyzer.depth_levels == 5
        assert analyzer.iceberg_check_enabled is True

    @pytest.mark.asyncio
    async def test_get_market_imbalance_success(self, mock_suite):
        """Test successful market imbalance retrieval."""
        # Mock response with depth_imbalance attribute
        response = Mock()
        response.__getitem__ = Mock(return_value=1.8)
        response.__contains__ = Mock(return_value=True)
        mock_suite.orderbook.get_market_imbalance.return_value = response

        analyzer = OrderBookAnalyzer(mock_suite)
        imbalance = await analyzer.get_market_imbalance()

        assert imbalance == 1.8
        mock_suite.orderbook.get_market_imbalance.assert_called_with(levels=5)

    @pytest.mark.asyncio
    async def test_get_market_imbalance_no_orderbook(self, mock_suite):
        """Test market imbalance when orderbook is not available."""
        mock_suite.orderbook = None

        analyzer = OrderBookAnalyzer(mock_suite)
        imbalance = await analyzer.get_market_imbalance()

        assert imbalance is None

    @pytest.mark.asyncio
    async def test_get_market_imbalance_exception(self, mock_suite):
        """Test market imbalance when exception occurs."""
        mock_suite.orderbook.get_market_imbalance.side_effect = Exception("API Error")

        analyzer = OrderBookAnalyzer(mock_suite)
        imbalance = await analyzer.get_market_imbalance()

        assert imbalance is None

    @pytest.mark.asyncio
    async def test_detect_icebergs_success(self, mock_suite):
        """Test successful iceberg detection."""
        iceberg_data = {
            "iceberg_levels": [
                {"side": "bid", "price": 4995.0, "size": 100},
                {"side": "ask", "price": 5005.0, "size": 150}
            ]
        }
        mock_suite.orderbook.detect_iceberg_orders.return_value = iceberg_data

        analyzer = OrderBookAnalyzer(mock_suite)
        icebergs = await analyzer.detect_icebergs()

        assert len(icebergs) == 2
        assert icebergs[0]["side"] == "bid"
        assert icebergs[1]["side"] == "ask"

    @pytest.mark.asyncio
    async def test_detect_icebergs_no_orderbook(self, mock_suite):
        """Test iceberg detection when orderbook is not available."""
        mock_suite.orderbook = None

        analyzer = OrderBookAnalyzer(mock_suite)
        icebergs = await analyzer.detect_icebergs()

        assert icebergs == []

    @pytest.mark.asyncio
    async def test_confirm_long_entry_success(self, mock_suite):
        """Test successful long entry confirmation."""
        # Set up favorable conditions for long entry
        response = Mock()
        response.__getitem__ = Mock(return_value=1.8)  # Above threshold
        response.__contains__ = Mock(return_value=True)
        mock_suite.orderbook.get_market_imbalance.return_value = response
        mock_suite.orderbook.detect_iceberg_orders.return_value = {"iceberg_levels": []}

        analyzer = OrderBookAnalyzer(mock_suite)
        confirmed, details = await analyzer.confirm_long_entry()

        assert confirmed is True
        assert details["confirmed"] is True
        assert details["imbalance"] == 1.8
        assert "Long entry confirmed" in details["reason"]

    @pytest.mark.asyncio
    async def test_confirm_long_entry_insufficient_imbalance(self, mock_suite):
        """Test long entry rejection due to insufficient imbalance."""
        response = Mock()
        response.__getitem__ = Mock(return_value=1.2)  # Below threshold
        response.__contains__ = Mock(return_value=True)
        mock_suite.orderbook.get_market_imbalance.return_value = response

        analyzer = OrderBookAnalyzer(mock_suite)
        confirmed, details = await analyzer.confirm_long_entry()

        assert confirmed is False
        assert details["confirmed"] is False
        assert "Insufficient bid imbalance" in details["reason"]

    @pytest.mark.asyncio
    async def test_confirm_long_entry_iceberg_detected(self, mock_suite):
        """Test long entry rejection due to iceberg orders on ask side."""
        # Set up good imbalance but iceberg on ask
        response = Mock()
        response.__getitem__ = Mock(return_value=1.8)
        response.__contains__ = Mock(return_value=True)
        mock_suite.orderbook.get_market_imbalance.return_value = response

        iceberg_data = {
            "iceberg_levels": [
                {"side": "ask", "price": 5005.0, "size": 150}
            ]
        }
        mock_suite.orderbook.detect_iceberg_orders.return_value = iceberg_data

        analyzer = OrderBookAnalyzer(mock_suite)
        confirmed, details = await analyzer.confirm_long_entry()

        assert confirmed is False
        assert "iceberg orders on ask side" in details["reason"]

    @pytest.mark.asyncio
    async def test_confirm_short_entry_success(self, mock_suite):
        """Test successful short entry confirmation."""
        # Set up favorable conditions for short entry
        response = Mock()
        response.__getitem__ = Mock(return_value=0.5)  # Below threshold
        response.__contains__ = Mock(return_value=True)
        mock_suite.orderbook.get_market_imbalance.return_value = response
        mock_suite.orderbook.detect_iceberg_orders.return_value = {"iceberg_levels": []}

        analyzer = OrderBookAnalyzer(mock_suite)
        confirmed, details = await analyzer.confirm_short_entry()

        assert confirmed is True
        assert details["confirmed"] is True
        assert details["imbalance"] == 0.5
        assert "Short entry confirmed" in details["reason"]

    @pytest.mark.asyncio
    async def test_confirm_short_entry_insufficient_imbalance(self, mock_suite):
        """Test short entry rejection due to insufficient imbalance."""
        response = Mock()
        response.__getitem__ = Mock(return_value=0.8)  # Above threshold
        response.__contains__ = Mock(return_value=True)
        mock_suite.orderbook.get_market_imbalance.return_value = response

        analyzer = OrderBookAnalyzer(mock_suite)
        confirmed, details = await analyzer.confirm_short_entry()

        assert confirmed is False
        assert "Insufficient ask imbalance" in details["reason"]

    @pytest.mark.asyncio
    async def test_get_orderbook_pressure(self, mock_suite):
        """Test orderbook pressure calculation."""
        snapshot = {
            "bids": [
                {"price": 4998.0, "volume": 100},
                {"price": 4997.0, "volume": 150},
                {"price": 4996.0, "volume": 200}
            ],
            "asks": [
                {"price": 5002.0, "volume": 80},
                {"price": 5003.0, "volume": 120},
                {"price": 5004.0, "volume": 100}
            ]
        }
        mock_suite.orderbook.get_orderbook_snapshot.return_value = snapshot

        analyzer = OrderBookAnalyzer(mock_suite)
        pressure = await analyzer.get_orderbook_pressure()

        assert "bid_pressure" in pressure
        assert "ask_pressure" in pressure
        assert "net_pressure" in pressure
        assert "bid_volume" in pressure
        assert "ask_volume" in pressure

        # Check calculations
        bid_volume = 450  # 100 + 150 + 200
        ask_volume = 300  # 80 + 120 + 100
        total = bid_volume + ask_volume

        assert pressure["bid_volume"] == bid_volume
        assert pressure["ask_volume"] == ask_volume
        assert abs(pressure["bid_pressure"] - (bid_volume / total)) < 0.01
        assert abs(pressure["ask_pressure"] - (ask_volume / total)) < 0.01

    @pytest.mark.asyncio
    async def test_get_orderbook_pressure_no_data(self, mock_suite):
        """Test orderbook pressure with no data."""
        mock_suite.orderbook.get_orderbook_snapshot.return_value = None

        analyzer = OrderBookAnalyzer(mock_suite)
        pressure = await analyzer.get_orderbook_pressure()

        assert pressure["bid_pressure"] == 0
        assert pressure["ask_pressure"] == 0
        assert pressure["net_pressure"] == 0