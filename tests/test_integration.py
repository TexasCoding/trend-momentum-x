"""Integration tests for the complete trading strategy."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from project_x_py.event_bus import Event, EventType

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
            assert strategy.exit_manager is not None
            assert strategy.running is True

    @pytest.mark.asyncio
    async def test_volume_average_update(self, mock_suite, sample_1min_data):
        """Test volume average calculation."""
        with patch("main.TradingSuite.create", return_value=mock_suite):
            strategy = TrendMomentumXStrategy()
            await strategy.initialize()

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
            sample_ohlcv_data = sample_ohlcv_data.with_columns(volume=50)
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
            sample_ohlcv_data = sample_ohlcv_data.with_columns(volume=10)
            mock_suite.data.get_data.return_value = sample_ohlcv_data

            result = await strategy.check_volume_filter()

            assert result is False

    @pytest.mark.asyncio
    async def test_process_trading_signal_long_entry(self, mock_suite):
        """Test complete long entry signal processing."""
        with patch("main.TradingSuite.create", return_value=mock_suite):
            strategy = TrendMomentumXStrategy()
            await strategy.initialize()

            strategy.volume_avg_1min = 100.0

            with patch.object(strategy, 'check_volume_filter', new_callable=AsyncMock) as mock_vol, \
                 patch.object(strategy.trend_analyzer, 'get_trade_mode', new_callable=AsyncMock) as mock_mode, \
                 patch.object(strategy, 'check_long_entry', new_callable=AsyncMock) as mock_check_long:

                mock_vol.return_value = True
                mock_mode.return_value = "long_only"

                await strategy.process_trading_signal()

                mock_check_long.assert_called_once()

    @pytest.mark.asyncio
    async def test_enter_trade_complete_flow(self, mock_suite):
        """Test complete trade entry flow using managed_trade."""
        with patch("main.TradingSuite.create", return_value=mock_suite):
            strategy = TrendMomentumXStrategy()
            await strategy.initialize()

            with patch.object(strategy, '_calculate_stop_price', new_callable=AsyncMock) as mock_stop, \
                 patch.object(strategy, '_calculate_target_price') as mock_target:

                mock_stop.return_value = 4995.0
                mock_target.return_value = 5010.0
                mock_suite.data.get_current_price.return_value = 5000.0

                mock_managed_trade = AsyncMock()
                mock_managed_trade.enter_long.return_value = {"entry_order": MagicMock(id=12345)}
                
                async_cm = AsyncMock()
                async_cm.__aenter__.return_value = mock_managed_trade
                mock_suite.managed_trade.return_value = async_cm

                await strategy.enter_trade("long")

                mock_suite.managed_trade.assert_called_once()
                mock_managed_trade.enter_long.assert_called_once_with(
                    stop_loss=4995.0, take_profit=5010.0
                )
                assert "12345" in strategy.pending_orders

    @pytest.mark.asyncio
    async def test_on_order_filled(self, mock_suite):
        """Test order filled event handling."""
        with patch("main.TradingSuite.create", return_value=mock_suite):
            strategy = TrendMomentumXStrategy()
            await strategy.initialize()

            strategy.pending_orders["123"] = {"status": "pending"}
            mock_order = MagicMock(id=123, filledPrice=5000.0)
            event = Event(EventType.ORDER_FILLED, mock_order)

            await strategy.on_order_filled(event)

            assert strategy.pending_orders["123"]["status"] == "active"

    @pytest.mark.asyncio
    async def test_on_order_failed(self, mock_suite):
        """Test order failed event handling."""
        with patch("main.TradingSuite.create", return_value=mock_suite):
            strategy = TrendMomentumXStrategy()
            await strategy.initialize()

            strategy.pending_orders["123"] = {"status": "pending"}
            mock_order = MagicMock(id=123)
            event = Event(EventType.ORDER_REJECTED, mock_order)

            await strategy.on_order_failed(event)

            assert "123" not in strategy.pending_orders

    @pytest.mark.asyncio
    async def test_shutdown_closes_positions(self, mock_suite):
        """Test that shutdown closes all active positions."""
        with patch("main.TradingSuite.create", return_value=mock_suite):
            strategy = TrendMomentumXStrategy()
            await strategy.initialize()

            with patch.object(strategy.exit_manager, 'get_active_positions', return_value={"POS123": {}, "POS456": {}}):
                await strategy.shutdown()

                assert mock_suite.orders.close_position.call_count == 2
                mock_suite.orders.close_position.assert_any_call("POS123")
                mock_suite.orders.close_position.assert_any_call("POS456")
                mock_suite.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_long_entry_flow(self, mock_suite):
        """Test the complete long entry checking flow."""
        with patch("main.TradingSuite.create", return_value=mock_suite):
            strategy = TrendMomentumXStrategy()
            await strategy.initialize()

            with patch.object(strategy.signal_generator, 'check_long_entry', new_callable=AsyncMock) as mock_signal, \
                 patch.object(strategy.orderbook_analyzer, 'confirm_long_entry', new_callable=AsyncMock) as mock_ob, \
                 patch.object(strategy, 'enter_trade', new_callable=AsyncMock) as mock_enter:

                mock_signal.return_value = (True, {"signal": "valid"})
                mock_ob.return_value = (True, {"reason": "confirmed"})

                await strategy.check_long_entry()

                mock_enter.assert_called_with("long")

    @pytest.mark.asyncio
    async def test_check_short_entry_rejected_by_orderbook(self, mock_suite):
        """Test short entry rejected by orderbook analysis."""
        with patch("main.TradingSuite.create", return_value=mock_suite):
            strategy = TrendMomentumXStrategy()
            await strategy.initialize()

            with patch.object(strategy.signal_generator, 'check_short_entry', new_callable=AsyncMock) as mock_signal, \
                 patch.object(strategy.orderbook_analyzer, 'confirm_short_entry', new_callable=AsyncMock) as mock_ob, \
                 patch.object(strategy, 'enter_trade', new_callable=AsyncMock) as mock_enter:

                mock_signal.return_value = (True, {"signal": "valid"})
                mock_ob.return_value = (False, {"reason": "Iceberg detected"})

                await strategy.check_short_entry()

                mock_enter.assert_not_called()
