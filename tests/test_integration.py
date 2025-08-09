"""Integration tests for the complete trading strategy."""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from main import TrendMomentumXStrategy


class TestTrendMomentumXIntegration:
    """Integration tests for the complete strategy."""

    @pytest.mark.asyncio
    async def test_strategy_initialization(self, mock_suite):
        """Test complete strategy initialization."""
        with patch("main.TradingSuite.create", return_value=mock_suite):
            strategy = TrendMomentumXStrategy()
            await strategy.initialize()

            assert strategy.suite is not None
            assert strategy.trend_analyzer is not None
            assert strategy.signal_generator is not None
            assert strategy.orderbook_analyzer is not None
            assert strategy.risk_manager is not None
            assert strategy.exit_manager is not None
            assert strategy.running is True

    @pytest.mark.asyncio
    async def test_volume_average_update(self, mock_suite, sample_1min_data):
        """Test volume average calculation."""
        with patch("main.TradingSuite.create", return_value=mock_suite):
            strategy = TrendMomentumXStrategy()
            await strategy.initialize()

            # Set up mock data with volume
            sample_1min_data = sample_1min_data.with_columns(volume=100)
            mock_suite.data.get_data.return_value = sample_1min_data

            await strategy.update_volume_average()

            assert strategy.volume_avg_1min > 0
            mock_suite.data.get_data.assert_called_with("1min", bars=20)

    @pytest.mark.asyncio
    async def test_check_volume_filter_passed(self, mock_suite, sample_ohlcv_data):
        """Test volume filter when volume is sufficient."""
        with patch("main.TradingSuite.create", return_value=mock_suite):
            strategy = TrendMomentumXStrategy()
            await strategy.initialize()

            strategy.volume_avg_1min = 100.0
            sample_ohlcv_data = sample_ohlcv_data.with_columns(volume=50)  # Above 20% threshold
            mock_suite.data.get_data.return_value = sample_ohlcv_data

            result = await strategy.check_volume_filter()

            assert result is True

    @pytest.mark.asyncio
    async def test_check_volume_filter_failed(self, mock_suite, sample_ohlcv_data):
        """Test volume filter when volume is too low."""
        with patch("main.TradingSuite.create", return_value=mock_suite):
            strategy = TrendMomentumXStrategy()
            await strategy.initialize()

            strategy.volume_avg_1min = 100.0
            sample_ohlcv_data = sample_ohlcv_data.with_columns(volume=10)  # Below 20% threshold
            mock_suite.data.get_data.return_value = sample_ohlcv_data

            result = await strategy.check_volume_filter()

            assert result is False

    @pytest.mark.asyncio
    async def test_process_trading_signal_long_entry(self, mock_suite):
        """Test complete long entry signal processing."""
        with patch("main.TradingSuite.create", return_value=mock_suite):
            strategy = TrendMomentumXStrategy()
            await strategy.initialize()

            # Set up conditions for long entry
            strategy.volume_avg_1min = 100.0

            # Mock volume filter to pass
            strategy.check_volume_filter = AsyncMock(return_value=True)

            # Mock risk manager to allow trading
            strategy.risk_manager.can_trade = Mock(return_value=(True, "Trading allowed"))

            # Mock trend analyzer for long only mode
            strategy.trend_analyzer.get_trade_mode = AsyncMock(return_value="long_only")

            # Mock signal generator to return valid signal
            strategy.signal_generator.check_long_entry = AsyncMock(
                return_value=(True, {"rsi": 45, "wae": True})
            )

            # Mock orderbook confirmation
            strategy.orderbook_analyzer.confirm_long_entry = AsyncMock(
                return_value=(True, {"imbalance": 1.8})
            )

            # Mock enter_trade
            strategy.enter_trade = AsyncMock()

            await strategy.process_trading_signal()

            strategy.enter_trade.assert_called_with("long")

    @pytest.mark.asyncio
    async def test_process_trading_signal_blocked_by_risk(self, mock_suite):
        """Test signal blocked by risk management."""
        with patch("main.TradingSuite.create", return_value=mock_suite):
            strategy = TrendMomentumXStrategy()
            await strategy.initialize()

            strategy.check_volume_filter = AsyncMock(return_value=True)
            strategy.risk_manager.can_trade = Mock(return_value=(False, "Daily loss limit"))

            # Mock other methods that shouldn't be called
            strategy.trend_analyzer.get_trade_mode = AsyncMock()

            await strategy.process_trading_signal()

            # Should not check trade mode if risk blocks trading
            strategy.trend_analyzer.get_trade_mode.assert_not_called()

    @pytest.mark.asyncio
    async def test_enter_trade_complete_flow(self, mock_suite):
        """Test complete trade entry flow."""
        with patch("main.TradingSuite.create", return_value=mock_suite):
            strategy = TrendMomentumXStrategy()
            await strategy.initialize()

            # Set up mocks
            mock_suite.data.get_current_price.return_value = 5000.0
            strategy.risk_manager.calculate_stop_price = AsyncMock(return_value=4995.0)
            strategy.risk_manager.calculate_target_price = Mock(return_value=5010.0)
            strategy.risk_manager.calculate_position_size = AsyncMock(return_value=2)

            mock_suite.orders.place_bracket_order.return_value = "ORDER123"

            await strategy.enter_trade("long")

            # Verify order placement
            mock_suite.orders.place_bracket_order.assert_called_once()
            call_args = mock_suite.orders.place_bracket_order.call_args[1]
            assert call_args["side"] == 0  # Long
            assert call_args["size"] == 2
            assert call_args["entry_price"] == 5000.0
            assert call_args["stop_loss_price"] == 4995.0
            assert call_args["take_profit_price"] == 5010.0

            # Verify position added to risk manager
            assert strategy.risk_manager.add_position.called

    @pytest.mark.asyncio
    async def test_on_position_update_closed(self, mock_suite):
        """Test position update event handling."""
        with patch("main.TradingSuite.create", return_value=mock_suite):
            strategy = TrendMomentumXStrategy()
            await strategy.initialize()

            event = {
                "position_id": "POS123",
                "status": "closed",
                "pnl": 250.0
            }

            # Mock risk_manager methods
            strategy.risk_manager.remove_position = Mock()
            strategy.risk_manager.update_pnl = Mock()

            await strategy.on_position_update(event)

            strategy.risk_manager.remove_position.assert_called_with("POS123")
            strategy.risk_manager.update_pnl.assert_called_with(250.0)

    @pytest.mark.asyncio
    async def test_shutdown_closes_positions(self, mock_suite):
        """Test that shutdown closes all active positions."""
        with patch("main.TradingSuite.create", return_value=mock_suite):
            strategy = TrendMomentumXStrategy()
            await strategy.initialize()

            # Set up active positions
            strategy.exit_manager.get_active_positions = Mock(
                return_value={"POS123": {}, "POS456": {}}
            )

            await strategy.shutdown()

            # Verify positions were closed
            assert mock_suite.orders.close_position.call_count == 2
            mock_suite.orders.close_position.assert_any_call("POS123")
            mock_suite.orders.close_position.assert_any_call("POS456")

            # Verify cleanup was called
            mock_suite.data.cleanup.assert_called_once()
            mock_suite.orderbook.cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_daily_pnl_reset(self, mock_suite):
        """Test daily P&L reset at midnight."""
        with patch("main.TradingSuite.create", return_value=mock_suite):
            with patch("main.datetime") as mock_datetime:
                strategy = TrendMomentumXStrategy()
                await strategy.initialize()

                # Mock it's midnight
                mock_now = Mock()
                mock_now.hour = 0
                mock_now.minute = 0
                mock_datetime.now.return_value = mock_now

                # Create a simple run loop that executes once
                strategy.running = True

                async def stop_after_one():
                    await asyncio.sleep(0.1)
                    strategy.running = False

                task = asyncio.create_task(stop_after_one())
                # Mock reset_daily_pnl as a Mock object
                strategy.risk_manager.reset_daily_pnl = Mock()
                
                await strategy.run()
                await task

                strategy.risk_manager.reset_daily_pnl.assert_called()

    @pytest.mark.asyncio
    async def test_check_long_entry_flow(self, mock_suite):
        """Test the complete long entry checking flow."""
        with patch("main.TradingSuite.create", return_value=mock_suite):
            strategy = TrendMomentumXStrategy()
            await strategy.initialize()

            # Set up signal detection
            strategy.signal_generator.check_long_entry = AsyncMock(
                return_value=(True, {"signal": "valid"})
            )

            # Set up orderbook confirmation
            strategy.orderbook_analyzer.confirm_long_entry = AsyncMock(
                return_value=(True, {"reason": "confirmed"})
            )

            # Mock enter trade
            strategy.enter_trade = AsyncMock()

            await strategy.check_long_entry()

            strategy.enter_trade.assert_called_with("long")

    @pytest.mark.asyncio
    async def test_check_short_entry_rejected_by_orderbook(self, mock_suite):
        """Test short entry rejected by orderbook analysis."""
        with patch("main.TradingSuite.create", return_value=mock_suite):
            strategy = TrendMomentumXStrategy()
            await strategy.initialize()

            # Set up signal detection
            strategy.signal_generator.check_short_entry = AsyncMock(
                return_value=(True, {"signal": "valid"})
            )

            # Set up orderbook rejection
            strategy.orderbook_analyzer.confirm_short_entry = AsyncMock(
                return_value=(False, {"reason": "Iceberg detected"})
            )

            # Mock enter trade (should not be called)
            strategy.enter_trade = AsyncMock()

            await strategy.check_short_entry()

            strategy.enter_trade.assert_not_called()