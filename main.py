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
        self.logger = setup_logger(level=Config.LOG_LEVEL)
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
        self.last_event_time = None  # Track when we last received a real event

        # Cache latest bar data from events to avoid blocking get_data calls
        self.latest_bars = {
            "15sec": None,
            "1min": None,
            "5min": None,
            "15min": None
        }

        # -- Settings moved from custom RiskManager --
        self.atr_period = Config.ATR_PERIOD
        self.stop_ticks = Config.STOP_TICKS
        self.rr_ratio = Config.RR_RATIO

    async def initialize(self):
        self.logger.info("Initializing TrendMomentumX Strategy...")
        self.logger.info(f"Configuration: {Config.get_all_settings()}")

        try:
            self.suite = await TradingSuite.create(
                instrument=Config.INSTRUMENT,
                timeframes=Config.TIMEFRAMES,
                initial_days=5,
                features=["orderbook", "risk_manager"],  # Enable orderbook and risk manager
            )

            self.trend_analyzer = TrendAnalyzer(self.suite)
            self.signal_generator = SignalGenerator(self.suite)
            self.orderbook_analyzer = OrderBookAnalyzer(self.suite)
            self.exit_manager = ExitManager(self.suite)

            # Subscribe to events using the TradingSuite's on method directly
            await self.suite.on(EventType.NEW_BAR, self.on_new_bar)
            self.logger.debug("Subscribed to NEW_BAR events")
            await self.suite.on(EventType.ORDER_FILLED, self.on_order_filled)
            self.logger.debug("Subscribed to ORDER_FILLED events")
            await self.suite.on(EventType.ORDER_CANCELLED, self.on_order_failed)
            await self.suite.on(EventType.ORDER_REJECTED, self.on_order_failed)
            await self.suite.on(EventType.POSITION_CLOSED, self.on_position_closed)
            self.logger.info("Event subscriptions registered")

            # Debug: Check if we can get current data manually
            try:
                test_data = await self.suite.data.get_data("15sec", bars=2)
                if test_data is not None and len(test_data) > 0:
                    last_bar = test_data.tail(1)
                    self.logger.debug(f"Manual data check - Last 15sec bar: Close={last_bar['close'][0]:.2f}, Volume={last_bar['volume'][0]}")
                    # Also check timestamp to see how recent the data is
                    if 'timestamp' in test_data.columns:
                        last_time = test_data.tail(1)['timestamp'][0]
                        self.logger.debug(f"Last bar timestamp: {last_time}")
                else:
                    self.logger.warning("No data available from manual check")
            except Exception as e:
                self.logger.error(f"Error checking manual data: {e}")

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
        if data_1m is None:
            self.logger.error("No 1min data available")
            return entry_price

        if not data_1m.is_empty() and len(data_1m) >= self.atr_period:
            data_1m = data_1m.pipe(ATR, period=self.atr_period)
            atr_value = data_1m.tail(1)["atr_14"][0]
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

    async def on_new_bar(self, event: Any):
        """Handle new OHLCV bar events."""
        try:
            # Update last event time
            self.last_event_time = datetime.now()

            # Event structure from project-x-py: event.data contains {'timeframe': '...', 'data': {bar data}}
            data = event.data if hasattr(event, "data") else {}
            timeframe = data.get("timeframe", "unknown")
            bar_data = data.get("data", {})

            # Cache the latest bar data for this timeframe
            if timeframe in self.latest_bars and bar_data:
                self.latest_bars[timeframe] = {
                    "timestamp": datetime.now(),
                    "data": bar_data
                }

            self.logger.debug(
                f"New {timeframe} bar: "
                f"C={bar_data.get('close', 0):.2f} V={bar_data.get('volume', 0)}"
            )

            if not self.running:
                return

            # Only process signals on the primary timeframe (15sec)
            if timeframe != "15sec":
                # Update 1-minute volume average on 1-minute bars
                if timeframe == "1min" and bar_data:
                    self.logger.debug("Updating 1-minute volume average from cached data")
                    # Update volume average directly from the event data
                    self.update_volume_average_from_event(bar_data)
                return

            self.logger.debug("Processing trading signal for 15sec timeframe")
            # Instead of processing immediately, create a task to process outside event handler
            asyncio.create_task(self._process_signal_task(bar_data))
        except Exception as e:
            self.logger.error(f"Error processing new bar event: {e}", exc_info=True)
            # Don't re-raise - keep event handler alive

    async def _process_signal_task(self, bar_data: dict):
        """Process signal in a separate task outside event handler context."""
        try:
            # Process immediately - asyncio.create_task already ensures we're in a separate context
            await self.process_trading_signal()
        except Exception as e:
            self.logger.error(f"Error in signal processing task: {e}", exc_info=True)

    def update_volume_average_from_event(self, bar_data: dict):
        """Update volume average from event data without fetching."""
        try:
            volume = bar_data.get("volume", 0)
            # Simple moving average update (approximate)
            if self.volume_avg_1min == 0:
                self.volume_avg_1min = float(volume)
            else:
                # Exponential moving average for simplicity
                alpha = 0.1  # Smoothing factor
                self.volume_avg_1min = alpha * float(volume) + (1 - alpha) * self.volume_avg_1min
            self.logger.debug(f"Updated volume average to {self.volume_avg_1min:.2f}")
        except Exception as e:
            self.logger.error(f"Error updating volume average from event: {e}")

    async def update_volume_average(self):
        """Legacy method - now uses cached data."""
        try:
            if not self.suite:
                self.logger.error("TradingSuite not initialized, skipping volume average update")
                return
            # Try to use cached data first
            if self.latest_bars.get("1min"):
                bar_data = self.latest_bars["1min"].get("data", {})
                self.update_volume_average_from_event(bar_data)
                return

            # Fallback to fetching (with timeout)
            try:
                data_1m = await asyncio.wait_for(
                    self.suite.data.get_data("1min", bars=20),
                    timeout=2.0
                )
                if data_1m is None:
                    self.logger.error("No 1min data available")
                    return

                if not data_1m.is_empty() and len(data_1m) >= 20:
                    volume_series = data_1m.select("volume").tail(20)
                    if volume_series is not None and len(volume_series) > 0:
                        mean_value = volume_series["volume"].mean()
                        if isinstance(mean_value, int | float):
                            self.volume_avg_1min = float(mean_value)
                        else:
                            self.volume_avg_1min = 0.0
            except TimeoutError:
                self.logger.error("Timeout fetching 1min data for volume average")
        except Exception as e:
            self.logger.error(f"Error updating volume average: {e}")

    async def process_trading_signal_with_cached_data(self, bar_data: dict):
        """Process trading signal using cached bar data from event."""
        try:
            self.logger.debug("Starting process_trading_signal_with_cached_data")

            # Quick volume check using cached data
            current_volume = bar_data.get("volume", 0)

            # Skip if no volume average established yet
            if self.volume_avg_1min <= 0:
                self.logger.debug("Volume average not established, skipping")
                return

            # Check volume threshold
            if current_volume < Config.VOLUME_THRESHOLD_PERCENT * self.volume_avg_1min:
                self.logger.debug(f"Volume too low: {current_volume} < {Config.VOLUME_THRESHOLD_PERCENT * self.volume_avg_1min:.2f}")
                return

            self.logger.debug(f"Volume check passed: {current_volume} >= {Config.VOLUME_THRESHOLD_PERCENT * self.volume_avg_1min:.2f}")

            if not self.trend_analyzer:
                self.logger.error("TrendAnalyzer not initialized, skipping")
                return

            # Get trade mode - this still needs to fetch data, so add timeout
            self.logger.debug("Getting trade mode from trend analyzer")
            try:
                trade_mode = await asyncio.wait_for(
                    self.trend_analyzer.get_trade_mode(),
                    timeout=3.0
                )
                self.logger.debug(f"Trade mode: {trade_mode}")
            except TimeoutError:
                self.logger.error("Timeout getting trade mode")
                return

            if trade_mode == "no_trade":
                self.logger.debug("Trade mode is no_trade, skipping")
                return

            if trade_mode == "long_only":
                self.logger.debug("Checking long entry")
                await self.check_long_entry()
            elif trade_mode == "short_only":
                self.logger.debug("Checking short entry")
                await self.check_short_entry()

            self.logger.debug("Finished process_trading_signal_with_cached_data")

        except Exception as e:
            self.logger.error(f"Error in process_trading_signal_with_cached_data: {e}", exc_info=True)

    async def process_trading_signal(self):
        # The managed_trade context will handle pre-trade risk checks.
        # If risk limits (e.g., max daily loss) are hit, it will raise an exception.
        try:
            self.logger.debug("Starting process_trading_signal")

            self.logger.debug("About to check volume filter")
            volume_ok = await self.check_volume_filter()
            self.logger.debug(f"Volume filter result: {volume_ok}")

            if self.orderbook_analyzer:
                current_imbalance = await self.orderbook_analyzer.get_market_imbalance()
                self.logger.debug(f"Current imbalance: {current_imbalance}")

            if not volume_ok:
                self.logger.debug("Volume filter check failed, skipping trade signal")
                return

            if not self.trend_analyzer:
                self.logger.error("TrendAnalyzer not initialized, skipping trade signal")
                return

            self.logger.debug("Getting trade mode from trend analyzer")
            trade_mode = await self.trend_analyzer.get_trade_mode()
            self.logger.debug(f"Trade mode: {trade_mode}")

            if trade_mode == "no_trade":
                self.logger.debug("Trade mode is no_trade, skipping")
                return

            if trade_mode == "long_only":
                self.logger.debug("Checking long entry")
                await self.check_long_entry()
            elif trade_mode == "short_only":
                self.logger.debug("Checking short entry")
                await self.check_short_entry()

            self.logger.debug("Finished process_trading_signal")

        except Exception as e:
            # Catch exceptions from managed_trade if risk limits are violated
            self.logger.error(f"Could not process trade signal: {e}", exc_info=True)
            raise  # Re-raise to be caught by the caller

    async def check_volume_filter(self) -> bool:
        try:
            self.logger.debug("check_volume_filter: Starting")
            if not self.suite:
                self.logger.error("TradingSuite not initialized, skipping volume filter check")
                return False

            self.logger.debug("check_volume_filter: Getting 15sec data")
            data_15s = await self.suite.data.get_data("15sec", bars=1)

            if data_15s is None:
                self.logger.error("No 15sec data available")
                return False
            self.logger.debug(f"check_volume_filter: Got data, length={len(data_15s)}")

            if data_15s.is_empty():
                self.logger.debug("No data available for volume filter check")
                return False

            current_volume = data_15s.tail(1)["volume"][0]
            self.logger.debug(f"check_volume_filter: current_volume={current_volume}, avg={self.volume_avg_1min}")

            # Require volume average to be established before trading
            if self.volume_avg_1min <= 0:
                self.logger.debug("Volume average not established, skipping volume filter check")
                return False

            result = bool(current_volume >= Config.VOLUME_THRESHOLD_PERCENT * self.volume_avg_1min)
            self.logger.debug(f"check_volume_filter: returning {result}")
            return result

        except Exception as e:
            self.logger.error(f"Error checking volume filter: {e}", exc_info=True)
            return False

    async def check_long_entry(self):
        if not self.signal_generator:
            self.logger.error("SignalGenerator not initialized, skipping long entry check")
            return
        signal_valid, signal_details = await self.signal_generator.check_long_entry()

        if not signal_valid:
            return

        self.logger.info(f"Long signal detected: {signal_details}")

        if not self.orderbook_analyzer:
            self.logger.error("OrderBookAnalyzer not initialized, skipping long entry check")
            return
        orderbook_confirmed, orderbook_details = await self.orderbook_analyzer.confirm_long_entry()

        if not orderbook_confirmed:
            self.logger.debug(f"Long signal rejected by orderbook: {orderbook_details['reason']}")
            return

        self.logger.info("Long entry confirmed by orderbook")
        await self.enter_trade("long")

    async def check_short_entry(self):
        if not self.signal_generator:
            self.logger.error("SignalGenerator not initialized, skipping short entry check")
            return
        signal_valid, signal_details = await self.signal_generator.check_short_entry()

        if not signal_valid:
            return

        self.logger.info(f"Short signal detected: {signal_details}")

        if not self.orderbook_analyzer:
            self.logger.error("OrderBookAnalyzer not initialized, skipping short entry check")
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

        # Create a heartbeat task to log periodically
        async def heartbeat():
            check_count = 0
            while self.running:
                await asyncio.sleep(30)  # Log every 30 seconds
                if self.running:
                    check_count += 1
                    # Check how long since last event
                    time_since_event = "Never"
                    if self.last_event_time:
                        seconds_since = (datetime.now() - self.last_event_time).total_seconds()
                        time_since_event = f"{seconds_since:.0f}s ago"
                    self.logger.debug(f"Strategy heartbeat - Running, volume_avg: {self.volume_avg_1min:.2f}, last event: {time_since_event}")

                    # Every minute, check if we can get data manually
                    if check_count % 2 == 0 and self.suite:
                        try:
                            data_15s = await self.suite.data.get_data("15sec", bars=1)
                            if data_15s is not None and len(data_15s) > 0:
                                last_close = data_15s.tail(1)['close'][0]
                                self.logger.debug(f"Manual data poll - 15sec close: {last_close:.2f}")
                            else:
                                self.logger.warning("Heartbeat: No 15sec data available")
                        except Exception as e:
                            self.logger.error(f"Heartbeat data check error: {e}")

        heartbeat_task = asyncio.create_task(heartbeat())

        try:
            # Keep the event loop active - don't just wait on stop_event
            while self.running:
                await asyncio.sleep(0.1)  # Yield control to event loop frequently
                if self.stop_event.is_set():
                    break
        except asyncio.CancelledError:
            self.logger.info("Strategy run cancelled")
        finally:
            heartbeat_task.cancel()
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
