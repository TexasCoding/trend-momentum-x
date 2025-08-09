import asyncio
import signal
import sys
from datetime import datetime
from typing import Any

from project_x_py import TradingSuite

from strategy import ExitManager, OrderBookAnalyzer, RiskManager, SignalGenerator, TrendAnalyzer
from utils import Config, setup_logger


class TrendMomentumXStrategy:
    def __init__(self):
        self.logger = setup_logger()
        self.suite: TradingSuite | None = None
        self.trend_analyzer: TrendAnalyzer | None = None
        self.signal_generator: SignalGenerator | None = None
        self.orderbook_analyzer: OrderBookAnalyzer | None = None
        self.risk_manager: RiskManager | None = None
        self.exit_manager: ExitManager | None = None
        self.running = False
        self.volume_avg_1min = 0.0
        self.pending_orders: dict[str, dict] = {}  # Track pending orders
        self.last_daily_reset = datetime.now().date()
        self.last_weekly_reset = datetime.now().date()

    async def initialize(self):
        self.logger.info("Initializing TrendMomentumX Strategy...")
        self.logger.info(f"Configuration: {Config.get_all_settings()}")

        try:
            self.suite = await TradingSuite.create(
                Config.INSTRUMENT, **Config.get_trading_suite_config()
            )

            self.trend_analyzer = TrendAnalyzer(self.suite)
            self.signal_generator = SignalGenerator(self.suite)
            self.orderbook_analyzer = OrderBookAnalyzer(self.suite)
            self.risk_manager = RiskManager(self.suite)
            self.exit_manager = ExitManager(self.suite)

            # Subscribe to events using the EventBus
            if hasattr(self.suite, "event_bus"):
                await self.suite.events.on("new_bar", self.on_new_bar)
                await self.suite.events.on("position_update", self.on_position_update)
                self.logger.info("Event subscriptions registered")
            else:
                self.logger.warning("EventBus not found, cannot subscribe to events")

            self.logger.info("Strategy initialized successfully")
            self.running = True

        except Exception as e:
            self.logger.error(f"Failed to initialize strategy: {e}")
            raise

    async def on_new_bar(self, event_data):
        _ = event_data  # Event data may be used in future implementations
        if not self.running:
            return

        # Process all timeframes since we get all bar updates
        await self.update_volume_average()
        await self.process_trading_signal()

    async def update_volume_average(self):
        try:
            if not self.suite:
                return
            data_1m = await self.suite.data.get_data("1min", bars=20)
            if data_1m is not None and len(data_1m) >= 20:
                volume_series = data_1m.select("volume").tail(20)
                if volume_series is not None and len(volume_series) > 0:
                    mean_value = volume_series["volume"].mean()
                    if isinstance(mean_value, int | float):
                        self.volume_avg_1min = float(mean_value)
                    else:
                        self.volume_avg_1min = 0.0
        except Exception as e:
            self.logger.error(f"Error updating volume average: {e}")

    async def process_trading_signal(self):
        try:
            if not await self.check_volume_filter():
                return

            if not self.risk_manager:
                return
            can_trade, reason = self.risk_manager.can_trade()
            if not can_trade:
                self.logger.debug(f"Trading not allowed: {reason}")
                return

            if not self.trend_analyzer:
                return
            trade_mode = await self.trend_analyzer.get_trade_mode()

            if trade_mode == "no_trade":
                return

            if trade_mode == "long_only":
                await self.check_long_entry()
            elif trade_mode == "short_only":
                await self.check_short_entry()

        except Exception as e:
            self.logger.error(f"Error processing trading signal: {e}")

    async def check_volume_filter(self) -> bool:
        try:
            if not self.suite:
                return False
            data_15s = await self.suite.data.get_data("15s", bars=1)
            if data_15s is None or len(data_15s) == 0:
                return False

            current_volume = data_15s.tail(1)["volume"][0]

            # Require volume average to be established before trading
            if self.volume_avg_1min <= 0:
                return False

            return bool(current_volume >= Config.VOLUME_THRESHOLD_PERCENT * self.volume_avg_1min)

        except Exception as e:
            self.logger.error(f"Error checking volume filter: {e}")
            return False

    async def check_long_entry(self):
        if not self.signal_generator:
            return
        signal_valid, signal_details = await self.signal_generator.check_long_entry()

        if not signal_valid:
            return

        self.logger.info(f"Long signal detected: {signal_details}")

        if not self.orderbook_analyzer:
            return
        orderbook_confirmed, orderbook_details = await self.orderbook_analyzer.confirm_long_entry()

        if not orderbook_confirmed:
            self.logger.debug(f"Long signal rejected by orderbook: {orderbook_details['reason']}")
            return

        self.logger.info("Long entry confirmed by orderbook")
        await self.enter_trade("long")

    async def check_short_entry(self):
        if not self.signal_generator:
            return
        signal_valid, signal_details = await self.signal_generator.check_short_entry()

        if not signal_valid:
            return

        self.logger.info(f"Short signal detected: {signal_details}")

        if not self.orderbook_analyzer:
            return
        orderbook_confirmed, orderbook_details = await self.orderbook_analyzer.confirm_short_entry()

        if not orderbook_confirmed:
            self.logger.debug(f"Short signal rejected by orderbook: {orderbook_details['reason']}")
            return

        self.logger.info("Short entry confirmed by orderbook")
        await self.enter_trade("short")

    async def enter_trade(self, direction: str):
        try:
            if not self.suite:
                return
            current_price = await self.suite.data.get_current_price()
            if not current_price:
                self.logger.error("Unable to get current price")
                return

            # Calculate slippage based on instrument tick size
            slippage_ticks = 2  # Conservative 2 tick slippage
            if self.suite.instrument and hasattr(self.suite.instrument, "tickSize"):
                tick_size = self.suite.instrument.tickSize
                slippage = slippage_ticks * tick_size

                # Adjust entry price for expected slippage
                if direction == "long":
                    entry_price = current_price + slippage
                else:
                    entry_price = current_price - slippage
            else:
                entry_price = current_price

            if not self.risk_manager:
                return
            stop_price = await self.risk_manager.calculate_stop_price(entry_price, direction)
            target_price = self.risk_manager.calculate_target_price(
                entry_price, stop_price, direction
            )

            position_size = await self.risk_manager.calculate_position_size(entry_price, stop_price)

            if not position_size or position_size <= 0:
                self.logger.error("Invalid position size calculated")
                return

            side = 0 if direction == "long" else 1

            self.logger.info(
                f"Placing {direction} order: "
                f"Size={position_size}, Entry={entry_price:.2f}, "
                f"Stop={stop_price:.2f}, Target={target_price:.2f}"
            )

            if not self.suite:
                return
            response = await self.suite.orders.place_bracket_order(
                contract_id=str(self.suite.instrument.id) if self.suite.instrument else "0",
                side=side,
                size=position_size,
                entry_price=entry_price,
                stop_loss_price=stop_price,
                take_profit_price=target_price,
            )

            if response:
                order_id = str(response) if response else None
                position = {
                    "id": order_id,
                    "direction": direction,
                    "entry_price": entry_price,
                    "stop_price": stop_price,
                    "target_price": target_price,
                    "size": position_size,
                    "status": "pending",
                    "created_at": datetime.now(),
                }

                # Track pending order
                if order_id:
                    self.pending_orders[order_id] = position

                if self.risk_manager:
                    self.risk_manager.add_position(position)

                if self.exit_manager:
                    asyncio.create_task(self.exit_manager.manage_position(position))

                self.logger.info(f"Order placed successfully: {response}")
            else:
                self.logger.error(f"Failed to place order: {response}")

        except Exception as e:
            self.logger.error(f"Error entering trade: {e}")

    async def on_position_update(self, event):
        position_id = event.get("position_id")
        status = event.get("status")
        pnl = event.get("pnl", 0)

        # Update pending order status
        if position_id in self.pending_orders:
            if status == "filled":
                self.pending_orders[position_id]["status"] = "active"
                self.logger.info(f"Order {position_id} filled")
            elif status == "cancelled" or status == "rejected":
                # Remove from tracking if order failed
                del self.pending_orders[position_id]
                if self.risk_manager:
                    self.risk_manager.remove_position(position_id)
                self.logger.warning(f"Order {position_id} {status}")

        if status == "closed":
            if position_id in self.pending_orders:
                del self.pending_orders[position_id]
            if self.risk_manager:
                self.risk_manager.remove_position(position_id)
                self.risk_manager.update_pnl(pnl)
            self.logger.info(f"Position {position_id} closed with P&L: {pnl:.2f}")

    async def run(self):
        await self.initialize()

        self.logger.info(f"Strategy running in {Config.TRADING_MODE} mode")
        self.logger.info("Press Ctrl+C to stop")

        try:
            while self.running:
                await asyncio.sleep(1)

                # Check for daily reset (once per day at midnight)
                current_date = datetime.now().date()
                if current_date > self.last_daily_reset:
                    if self.risk_manager:
                        self.risk_manager.reset_daily_pnl()
                    self.logger.info("Daily P&L reset")
                    self.last_daily_reset = current_date

                # Check for weekly reset (Monday at midnight)
                if current_date.weekday() == 0 and current_date > self.last_weekly_reset:
                    if self.risk_manager:
                        self.risk_manager.reset_weekly_pnl()
                    self.logger.info("Weekly P&L reset")
                    self.last_weekly_reset = current_date

        except asyncio.CancelledError:
            self.logger.info("Strategy cancelled")
        finally:
            await self.shutdown()

    async def shutdown(self):
        self.logger.info("Shutting down strategy...")
        self.running = False

        active_positions = self.exit_manager.get_active_positions() if self.exit_manager else {}
        if active_positions:
            self.logger.warning(f"Closing {len(active_positions)} active positions...")
            for position_id in active_positions:
                try:
                    if self.suite:
                        await self.suite.orders.close_position(position_id)
                except Exception as e:
                    self.logger.error(f"Failed to close position {position_id}: {e}")

        if self.suite:
            # Cleanup resources
            if self.suite.data:
                await self.suite.data.cleanup()
            if self.suite.orderbook:
                await self.suite.orderbook.cleanup()

        self.logger.info("Strategy shutdown complete")


def signal_handler(sig: int, frame: Any) -> None:
    _ = sig  # Signal number
    _ = frame  # Current stack frame
    print("\nReceived interrupt signal, shutting down...")
    sys.exit(0)


async def main():
    signal.signal(signal.SIGINT, signal_handler)

    strategy = TrendMomentumXStrategy()

    try:
        await strategy.run()
    except KeyboardInterrupt:
        print("\nKeyboard interrupt received")
    except Exception as e:
        print(f"Strategy error: {e}")
    finally:
        await strategy.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
