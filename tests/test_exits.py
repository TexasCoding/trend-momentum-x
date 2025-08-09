"""Unit tests for the exits module."""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from strategy.exits import ExitManager


class TestExitManager:
    """Test suite for ExitManager class."""

    @pytest.mark.asyncio
    async def test_initialization(self, mock_suite):
        """Test ExitManager initialization."""
        manager = ExitManager(mock_suite)
        assert manager.suite == mock_suite
        assert manager.time_exit_minutes == 5
        assert manager.breakeven_trigger_ratio == 1.0
        assert manager.breakeven_offset_ticks == 5
        assert manager.trailing_enabled is True
        assert len(manager.active_positions) == 0

    @pytest.mark.asyncio
    async def test_manage_position_adds_to_active(self, mock_suite):
        """Test that manage_position adds position to active positions."""
        manager = ExitManager(mock_suite)
        mock_suite.data.get_current_price.return_value = 5000.0

        position = {
            "id": "POS123",
            "entry_price": 5000.0,
            "stop_price": 4995.0,
            "target_price": 5010.0,
            "direction": "long",
            "size": 2
        }

        # Start managing position
        task = asyncio.create_task(manager.manage_position(position))
        await asyncio.sleep(0.1)  # Let it initialize

        assert "POS123" in manager.active_positions
        assert manager.active_positions["POS123"]["entry_price"] == 5000.0

        # Cancel the task
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_check_exit_conditions_target_reached_long(self, mock_suite):
        """Test exit condition when target is reached for long position."""
        manager = ExitManager(mock_suite)
        mock_suite.data.get_current_price.return_value = 5010.0

        manager.active_positions["POS123"] = {
            "entry_time": datetime.now(),
            "entry_price": 5000.0,
            "stop_price": 4995.0,
            "target_price": 5010.0,
            "direction": "long",
            "size": 2
        }

        result = await manager._check_exit_conditions("POS123")

        assert result["should_exit"] is True
        assert result["reason"] == "Target reached"

    @pytest.mark.asyncio
    async def test_check_exit_conditions_stop_hit_long(self, mock_suite):
        """Test exit condition when stop loss is hit for long position."""
        manager = ExitManager(mock_suite)
        mock_suite.data.get_current_price.return_value = 4995.0

        manager.active_positions["POS123"] = {
            "entry_time": datetime.now(),
            "entry_price": 5000.0,
            "stop_price": 4995.0,
            "target_price": 5010.0,
            "direction": "long",
            "size": 2
        }

        result = await manager._check_exit_conditions("POS123")

        assert result["should_exit"] is True
        assert result["reason"] == "Stop loss hit"

    @pytest.mark.asyncio
    async def test_check_exit_conditions_time_exit(self, mock_suite):
        """Test exit condition based on time without progress."""
        manager = ExitManager(mock_suite)
        mock_suite.data.get_current_price.return_value = 4999.0  # Below entry

        manager.active_positions["POS123"] = {
            "entry_time": datetime.now() - timedelta(minutes=6),  # 6 minutes ago
            "entry_price": 5000.0,
            "stop_price": 4995.0,
            "target_price": 5010.0,
            "direction": "long",
            "size": 2
        }

        result = await manager._check_exit_conditions("POS123")

        assert result["should_exit"] is True
        assert "Time exit" in result["reason"]

    @pytest.mark.asyncio
    async def test_check_trend_reversal_long_to_bearish(self, mock_suite):
        """Test trend reversal detection for long position."""
        manager = ExitManager(mock_suite)

        # Mock TrendAnalyzer to return bearish trend
        with patch("strategy.trend_analysis.TrendAnalyzer") as MockTrendAnalyzer:
            mock_analyzer = MockTrendAnalyzer.return_value
            mock_analyzer.get_5min_trend = AsyncMock(return_value="bearish")

            result = await manager._check_trend_reversal("long")

            assert result is True

    @pytest.mark.asyncio
    async def test_check_trend_reversal_short_to_bullish(self, mock_suite):
        """Test trend reversal detection for short position."""
        manager = ExitManager(mock_suite)

        # Mock TrendAnalyzer to return bullish trend
        with patch("strategy.trend_analysis.TrendAnalyzer") as MockTrendAnalyzer:
            mock_analyzer = MockTrendAnalyzer.return_value
            mock_analyzer.get_5min_trend = AsyncMock(return_value="bullish")

            result = await manager._check_trend_reversal("short")

            assert result is True

    @pytest.mark.asyncio
    async def test_check_trailing_activation_long(self, mock_suite):
        """Test trailing stop activation for long position."""
        manager = ExitManager(mock_suite)
        mock_suite.data.get_current_price.return_value = 5006.0  # Above breakeven trigger

        manager.active_positions["POS123"] = {
            "entry_price": 5000.0,
            "stop_price": 4995.0,
            "direction": "long",
            "trailing_stop_activated": False,
            "breakeven_activated": False
        }

        await manager._check_trailing_activation("POS123")

        assert manager.active_positions["POS123"]["trailing_stop_activated"] is True

    @pytest.mark.asyncio
    async def test_move_stop_to_breakeven(self, mock_suite):
        """Test moving stop to breakeven."""
        manager = ExitManager(mock_suite)
        mock_suite.instrument.tickSize = 0.25

        manager.active_positions["POS123"] = {
            "entry_price": 5000.0,
            "stop_price": 4995.0,
            "direction": "long",
            "breakeven_activated": False
        }

        await manager._move_stop_to_breakeven("POS123")

        # New stop should be entry + offset
        expected_stop = 5000.0 + (5 * 0.25)  # 5 ticks offset
        assert manager.active_positions["POS123"]["stop_price"] == expected_stop
        assert manager.active_positions["POS123"]["breakeven_activated"] is True

    @pytest.mark.asyncio
    async def test_update_trailing_stop_long(self, mock_suite, sample_ohlcv_data):
        """Test trailing stop update for long position."""
        from project_x_py.indicators import SAR

        data_with_sar = sample_ohlcv_data.pipe(SAR)
        data_with_sar = data_with_sar.with_columns(SAR=4998.0)  # SAR below current price
        mock_suite.data.get_data.return_value = data_with_sar
        mock_suite.data.get_current_price.return_value = 5005.0

        manager = ExitManager(mock_suite)
        manager.active_positions["POS123"] = {
            "stop_price": 4995.0,
            "direction": "long"
        }

        await manager._update_trailing_stop("POS123")

        # Stop should be updated to SAR value
        assert manager.active_positions["POS123"]["stop_price"] == 4998.0

    @pytest.mark.asyncio
    async def test_exit_position(self, mock_suite):
        """Test position exit."""
        manager = ExitManager(mock_suite)
        manager.active_positions["POS123"] = {
            "entry_price": 5000.0,
            "stop_price": 4995.0
        }

        await manager._exit_position("POS123", "Target reached")

        mock_suite.orders.close_position.assert_called_with("POS123")
        assert "POS123" not in manager.active_positions

    def test_get_active_positions(self, mock_suite):
        """Test getting active positions."""
        manager = ExitManager(mock_suite)
        manager.active_positions = {
            "POS123": {"entry_price": 5000.0},
            "POS456": {"entry_price": 5010.0}
        }

        positions = manager.get_active_positions()

        assert len(positions) == 2
        assert "POS123" in positions
        assert "POS456" in positions