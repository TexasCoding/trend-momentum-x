import asyncio
import signal
from datetime import datetime
from typing import Any

from project_x_py import Order, TradingSuite
from project_x_py.event_bus import Event, EventType
from project_x_py.indicators import ATR

from strategy import ExitManager, OrderBookAnalyzer, SignalGenerator, TrendAnalyzer
from utils import Config, setup_logger


class TrendMomentumXStrategy:
    def __init__(self):
        self.logger = setup_logger()
        self.suite: TradingSuite | None = None
        self.trend_analyzer: TrendAnalyzer | None = None
        self.signal_generator: SignalGenerator | None = None
        self.orderbook_analyzer: OrderBookAnalyzer | None = None
        self.exit_manager: ExitManager | None = None
        self.running = False
        self.stop_event = asyncio.Event()
        self.volume_avg_1min = 0.0
        self.pending_orders: dict[str, dict] = {}  # Track pending orders
        self.last_daily_reset = datetime.now().date()
        self.last_weekly_reset = datetime.now().date()

        # -- Settings moved from custom RiskManager --
        self.atr_period = Config.RSI_PERIOD  # NOTE: Using RSI_PERIOD for ATR
        self.stop_ticks = 10  # NOTE: Hardcoded value
        self.rr_ratio = Config.RR_RATIO

    async def initialize(self):
        self.logger.info("Initializing TrendMomentumX Strategy...")
        self.logger.info(f"Configuration: {Config.get_all_settings()}")

        try:
            self.suite = await TradingSuite.create(
                instrument=Config.INSTRUMENT,
                timeframes=Config.TIMEFRAMES,
                features=["orderbook", "risk_manager"],  # Enable orderbook and risk manager
            )

            self.trend_analyzer = TrendAnalyzer(self.suite)
            self.signal_generator = SignalGenerator(self.suite)
            self.orderbook_analyzer = OrderBookAnalyzer(self.suite)
            self.exit_manager = ExitManager(self.suite)

            # Subscribe to events using the EventBus
            if hasattr(self.suite, "events") and self.suite.events:
                await self.suite.events.on(EventType.NEW_BAR, self.on_new_bar)
                await self.suite.events.on(EventType.ORDER_FILLED, self.on_order_filled)
                await self.suite.events.on(EventType.ORDER_CANCELLED, self.on_order_failed)
                await self.suite.events.on(EventType.ORDER_REJECTED, self.on_order_failed)
                await self.suite.events.on(EventType.POSITION_CLOSED, self.on_position_closed)
                self.logger.info("Event subscriptions registered")
            else:
                self.logger.warning("EventBus not found, cannot subscribe to events")

            self.logger.info("Strategy initialized successfully")
            self.running = True

        except Exception as e:
            self.logger.error(f"Failed to initialize strategy: {e}")
            raise

    # -- Helper methods moved from custom RiskManager --
    async def _calculate_stop_price(self, entry_price: float, direction: str) -> float:
        if not self.suite:
            raise ValueError("TradingSuite not initialized")

        data_1m = await self.suite.data.get_data("1min")
        if data_1m is not None and len(data_1m) >= self.atr_period:
            data_1m = data_1m.pipe(ATR, period=self.atr_period)
            atr_value = data_1m.tail(1)["ATR_14"][0]
            stop_price = entry_price - atr_value if direction == "long" else entry_price + atr_value
        else:
            instrument = self.suite.instrument
            if instrument and hasattr(instrument, "tickSize"):
                tick_size = instrument.tickSize
                stop_distance = self.stop_ticks * tick_size
                stop_price = (
                    entry_price - stop_distance
                    if direction == "long"
                    else entry_price + stop_distance
                )
            else:
                # Fallback if instrument info is missing
                stop_distance = entry_price * 0.01
                stop_price = (
                    entry_price - stop_distance
                    if direction == "long"
                    else entry_price + stop_distance
                )
        return float(stop_price)

    def _calculate_target_price(
        self, entry_price: float, stop_price: float, direction: str
    ) -> float:
        stop_distance = abs(entry_price - stop_price)
        target_distance = stop_distance * self.rr_ratio
        target_price = (
            entry_price + target_distance if direction == "long" else entry_price - target_distance
        )
        return target_price

    async def on_new_bar(self, event: Event):
        event_data = event.data if hasattr(event, "data") else event
        if not self.running:
            return
        # Only process signals on the primary timeframe (15sec)
        if isinstance(event_data, dict) and event_data.get("timeframe") != "15sec":
            # Update 1-minute volume average on 1-minute bars
            if event_data.get("timeframe") == "1min":
                await self.update_volume_average()
            return

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
        # The managed_trade context will handle pre-trade risk checks.
        # If risk limits (e.g., max daily loss) are hit, it will raise an exception.
        try:
            if not await self.check_volume_filter():
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
            # Catch exceptions from managed_trade if risk limits are violated
            self.logger.warning(f"Could not process trade signal: {e}")

    async def check_volume_filter(self) -> bool:
        try:
            if not self.suite:
                return False
            data_15s = await self.suite.data.get_data("15sec", bars=1)
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
        if not self.suite:
            self.logger.error("TradingSuite not available.")
            return

        try:
            current_price = await self.suite.data.get_current_price()
            if not current_price:
                self.logger.error("Unable to get current price for trade entry.")
                return

            # 1. Calculate Stop and Target using our strategy's logic
            stop_price = await self._calculate_stop_price(current_price, direction)
            target_price = self._calculate_target_price(current_price, stop_price, direction)

            self.logger.info(
                f"Attempting to enter {direction} trade. "
                f"Entry ~{current_price:.2f}, Stop={stop_price:.2f}, Target={target_price:.2f}"
            )

            # 2. Use the managed_trade context for execution
            # It handles position sizing, risk checks, and order placement.
            async with self.suite.managed_trade() as trade:
                if direction == "long":
                    result = await trade.enter_long(stop_loss=stop_price, take_profit=target_price)
                else:
                    result = await trade.enter_short(stop_loss=stop_price, take_profit=target_price)

                entry_order: Order | None = result.get("entry_order")
                if entry_order and entry_order.id:
                    entry_order_id = str(entry_order.id)
                    self.logger.info(
                        f"Managed trade submitted successfully. Entry Order ID: {entry_order_id}"
                    )
                    # Optional: Track the pending order if needed for other logic
                    self.pending_orders[entry_order_id] = {
                        "id": entry_order_id,
                        "direction": direction,
                        "entry_price": current_price,
                        "stop_price": stop_price,
                        "target_price": target_price,
                        "status": "pending",
                        "created_at": datetime.now(),
                    }
                else:
                    self.logger.error(f"Managed trade failed to execute: {result}")

        except Exception as e:
            self.logger.error(f"Error entering managed trade: {e}", exc_info=True)

    async def on_order_filled(self, event: Event):
        order: Order = event.data
        order_id = str(order.id)

        if order_id in self.pending_orders:
            self.pending_orders[order_id]["status"] = "active"
            self.logger.info(f"Entry order {order_id} filled at {order.filledPrice}")
        else:
            # This could be a stop-loss or take-profit fill
            self.logger.info(
                f"Order {order_id} filled (likely SL/TP). Position will be closed by ExitManager."
            )

    async def on_order_failed(self, event: Event):
        order: Order = event.data
        order_id = str(order.id)
        event_name = event.type.name if isinstance(event.type, EventType) else str(event.type)

        if order_id in self.pending_orders:
            self.logger.warning(f"Entry order {order_id} failed with status: {event_name}")
            # The managed_trade context handles its own state, but we can remove from our pending tracker.
            del self.pending_orders[order_id]

    async def on_position_closed(self, event: Event):
        # This event is fired by the library's PositionManager.
        # The data contains the final trade details, including P&L.
        closed_position_data = event.data
        pnl = closed_position_data.get("profitAndLoss", 0.0)
        position_id = str(closed_position_data.get("positionId"))

        self.logger.info(f"Position {position_id} closed with P&L: {pnl:.2f}")
        # The library's risk manager automatically tracks P&L. No manual update needed.

    async def run(self):
        await self.initialize()
        self.running = True

        self.logger.info(f"Strategy running in {Config.TRADING_MODE} mode")
        self.logger.info("Press Ctrl+C to stop")

        try:
            await self.stop_event.wait()
        except asyncio.CancelledError:
            self.logger.info("Strategy run cancelled")
        finally:
            await self.shutdown()

    async def shutdown(self):
        if not self.running:
            return
        self.logger.info("Shutting down strategy...")
        self.running = False
        self.stop_event.set()

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
            await self.suite.disconnect()

        self.logger.info("Strategy shutdown complete")


def create_signal_handler(strategy: "TrendMomentumXStrategy"):
    def signal_handler(sig: int, frame: Any) -> None:
        _ = sig, frame  # Unused
        print("\nReceived interrupt signal, shutting down...")
        asyncio.create_task(strategy.shutdown())

    return signal_handler


async def main():
    strategy = TrendMomentumXStrategy()
    signal.signal(signal.SIGINT, create_signal_handler(strategy))

    try:
        await strategy.run()
    except KeyboardInterrupt:
        print("\nKeyboard interrupt received during setup")
    except Exception as e:
        print(f"Strategy error: {e}")
    finally:
        # Ensure shutdown is called even if run() fails
        await strategy.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
