"""Unit tests for the risk_manager module."""

import pytest

from strategy.risk_manager import RiskManager


class TestRiskManager:
    """Test suite for RiskManager class."""

    @pytest.mark.asyncio
    async def test_initialization(self, mock_suite):
        """Test RiskManager initialization."""
        manager = RiskManager(mock_suite)
        assert manager.suite == mock_suite
        assert manager.risk_per_trade == 0.005
        assert manager.max_daily_loss == 0.03
        assert manager.max_weekly_loss == 0.05
        assert manager.rr_ratio == 2
        assert manager.max_concurrent_trades == 3

    @pytest.mark.asyncio
    async def test_calculate_position_size_valid(self, mock_suite):
        """Test position size calculation with valid inputs."""
        manager = RiskManager(mock_suite)

        # Set up mock account and instrument
        mock_suite.client.get_account_info.return_value.balance = 100000
        mock_suite.instrument.tickValue = 12.50
        mock_suite.instrument.tickSize = 0.25

        position_size = await manager.calculate_position_size(5000.0, 4995.0)

        assert position_size is not None
        assert position_size >= 1
        assert isinstance(position_size, int)

    @pytest.mark.asyncio
    async def test_calculate_position_size_no_account_info(self, mock_suite):
        """Test position size calculation with no account info."""
        manager = RiskManager(mock_suite)
        mock_suite.client.get_account_info.return_value = None

        position_size = await manager.calculate_position_size(5000.0, 4995.0)
        assert position_size is None

    @pytest.mark.asyncio
    async def test_calculate_position_size_zero_balance(self, mock_suite):
        """Test position size calculation with zero balance."""
        manager = RiskManager(mock_suite)
        mock_suite.client.get_account_info.return_value.balance = 0

        position_size = await manager.calculate_position_size(5000.0, 4995.0)
        assert position_size is None

    @pytest.mark.asyncio
    async def test_calculate_stop_price_long_with_atr(self, mock_suite, sample_1min_data):
        """Test stop price calculation for long position with ATR."""
        from project_x_py.indicators import ATR

        data_with_atr = sample_1min_data.pipe(ATR, period=14)
        data_with_atr = data_with_atr.with_columns(ATR_14=2.5)  # Set ATR value
        mock_suite.data.get_data.return_value = data_with_atr

        manager = RiskManager(mock_suite)
        stop_price = await manager.calculate_stop_price(5000.0, "long")

        assert stop_price < 5000.0  # Stop should be below entry for long
        assert stop_price == 4997.5  # 5000 - 2.5 (ATR)

    @pytest.mark.asyncio
    async def test_calculate_stop_price_short_with_atr(self, mock_suite, sample_1min_data):
        """Test stop price calculation for short position with ATR."""
        from project_x_py.indicators import ATR

        data_with_atr = sample_1min_data.pipe(ATR, period=14)
        data_with_atr = data_with_atr.with_columns(ATR_14=2.5)  # Set ATR value
        mock_suite.data.get_data.return_value = data_with_atr

        manager = RiskManager(mock_suite)
        stop_price = await manager.calculate_stop_price(5000.0, "short")

        assert stop_price > 5000.0  # Stop should be above entry for short
        assert stop_price == 5002.5  # 5000 + 2.5 (ATR)

    @pytest.mark.asyncio
    async def test_calculate_stop_price_no_atr_data(self, mock_suite):
        """Test stop price calculation without ATR data."""
        mock_suite.data.get_data.return_value = None
        mock_suite.instrument.tickSize = 0.25

        manager = RiskManager(mock_suite)
        stop_price = await manager.calculate_stop_price(5000.0, "long")

        # Should use default stop ticks
        expected_stop = 5000.0 - (10 * 0.25)  # 10 ticks default
        assert stop_price == expected_stop

    def test_calculate_target_price_long(self, mock_suite):
        """Test target price calculation for long position."""
        manager = RiskManager(mock_suite)
        target = manager.calculate_target_price(5000.0, 4995.0, "long")

        risk = 5.0  # 5000 - 4995
        expected_target = 5000.0 + (risk * 2)  # 2:1 RR ratio
        assert target == expected_target

    def test_calculate_target_price_short(self, mock_suite):
        """Test target price calculation for short position."""
        manager = RiskManager(mock_suite)
        target = manager.calculate_target_price(5000.0, 5005.0, "short")

        risk = 5.0  # 5005 - 5000
        expected_target = 5000.0 - (risk * 2)  # 2:1 RR ratio
        assert target == expected_target

    def test_can_trade_allowed(self, mock_suite):
        """Test trading permission when all conditions are met."""
        manager = RiskManager(mock_suite)
        can_trade, reason = manager.can_trade()

        assert can_trade is True
        assert reason == "Trading allowed"

    def test_can_trade_daily_loss_limit(self, mock_suite):
        """Test trading blocked by daily loss limit."""
        manager = RiskManager(mock_suite)
        manager.daily_pnl = -0.04  # -4% loss

        can_trade, reason = manager.can_trade()

        assert can_trade is False
        assert "Daily loss limit" in reason

    def test_can_trade_weekly_loss_limit(self, mock_suite):
        """Test trading blocked by weekly loss limit."""
        manager = RiskManager(mock_suite)
        manager.weekly_pnl = -0.06  # -6% loss

        can_trade, reason = manager.can_trade()

        assert can_trade is False
        assert "Weekly loss limit" in reason

    def test_can_trade_max_positions(self, mock_suite):
        """Test trading blocked by max concurrent positions."""
        manager = RiskManager(mock_suite)
        manager.open_positions = [{"id": "1"}, {"id": "2"}, {"id": "3"}]

        can_trade, reason = manager.can_trade()

        assert can_trade is False
        assert "Max concurrent trades" in reason

    def test_update_pnl(self, mock_suite):
        """Test P&L update."""
        manager = RiskManager(mock_suite)
        initial_daily = manager.daily_pnl
        initial_weekly = manager.weekly_pnl

        manager.update_pnl(100.5)

        assert manager.daily_pnl == initial_daily + 100.5
        assert manager.weekly_pnl == initial_weekly + 100.5

    def test_reset_daily_pnl(self, mock_suite):
        """Test daily P&L reset."""
        manager = RiskManager(mock_suite)
        manager.daily_pnl = -500.0
        manager.weekly_pnl = -1000.0

        manager.reset_daily_pnl()

        assert manager.daily_pnl == 0
        assert manager.weekly_pnl == -1000.0  # Weekly should not change

    def test_reset_weekly_pnl(self, mock_suite):
        """Test weekly P&L reset."""
        manager = RiskManager(mock_suite)
        manager.daily_pnl = -500.0
        manager.weekly_pnl = -1000.0

        manager.reset_weekly_pnl()

        assert manager.weekly_pnl == 0
        assert manager.daily_pnl == -500.0  # Daily should not change

    def test_add_and_remove_position(self, mock_suite):
        """Test adding and removing positions."""
        manager = RiskManager(mock_suite)

        position = {
            "id": "POS123",
            "direction": "long",
            "entry_price": 5000.0,
            "size": 2
        }

        manager.add_position(position)
        assert len(manager.open_positions) == 1
        assert manager.open_positions[0]["id"] == "POS123"

        manager.remove_position("POS123")
        assert len(manager.open_positions) == 0

    def test_get_risk_metrics(self, mock_suite):
        """Test risk metrics retrieval."""
        manager = RiskManager(mock_suite)
        manager.daily_pnl = -0.001  # Small loss that doesn't trigger limit
        manager.weekly_pnl = -0.002  # Small loss that doesn't trigger limit
        manager.open_positions = [{"id": "1"}]

        metrics = manager.get_risk_metrics()

        assert metrics["daily_pnl"] == -0.001
        assert metrics["weekly_pnl"] == -0.002
        assert metrics["open_positions"] == 1
        assert metrics["max_positions"] == 3
        assert metrics["risk_per_trade"] == 0.005
        assert metrics["can_trade"] is True