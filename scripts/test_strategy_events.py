#!/usr/bin/env python3
"""Test that mimics the exact strategy initialization to debug events."""

import asyncio
import logging
from datetime import datetime
from typing import Any

from project_x_py import EventType, TradingSuite

from utils import Config

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Suppress some debug logs
logging.getLogger("project_x_py.realtime_data_manager").setLevel(logging.WARNING)
logging.getLogger("project_x_py.orderbook").setLevel(logging.WARNING)


async def main():
    """Test with exact same initialization as strategy."""
    logger.info("Starting strategy-like event test...")

    # Create suite EXACTLY like the strategy does
    suite = await TradingSuite.create(
        instrument=Config.INSTRUMENT,  # MES from config
        timeframes=Config.TIMEFRAMES,  # ['15sec', '1min', '5min', '15min']
        initial_days=5,
        features=["orderbook", "risk_manager"],  # Same features
    )

    logger.info("TradingSuite created with strategy settings")

    # Track events
    event_count = 0
    last_event_time = None

    async def on_new_bar(event: Any):
        """Handle new bar like the strategy."""
        nonlocal event_count, last_event_time
        try:
            event_count += 1
            last_event_time = datetime.now()

            # Same extraction as strategy
            data = event.data if hasattr(event, "data") else {}
            timeframe = data.get("timeframe", "unknown")
            bar_data = data.get("data", {})

            logger.info(
                f"📊 NEW_BAR #{event_count} [{timeframe}]: "
                f"Close={bar_data.get('close', 0):.2f} "
                f"Volume={bar_data.get('volume', 0)}"
            )

            # Only process 15sec like strategy
            if timeframe == "15sec":
                logger.info("  -> Would process trading signal here")

        except Exception as e:
            logger.error(f"Error in handler: {e}", exc_info=True)

    # Register handler EXACTLY like strategy
    await suite.on(EventType.NEW_BAR, on_new_bar)
    logger.debug("Subscribed to NEW_BAR events")

    # Also test the manual data check like strategy does
    try:
        test_data = await suite.data.get_data("15sec", bars=2)
        if test_data is not None and len(test_data) > 0:
            last_bar = test_data.tail(1)
            logger.debug(
                f"Manual data check - Last 15sec bar: "
                f"Close={last_bar['close'][0]:.2f}, Volume={last_bar['volume'][0]}"
            )
            if 'timestamp' in test_data.columns:
                last_time = test_data.tail(1)['timestamp'][0]
                logger.debug(f"Last bar timestamp: {last_time}")
        else:
            logger.warning("No data available from manual check")
    except Exception as e:
        logger.error(f"Error checking manual data: {e}")

    # Run for 2 minutes with status updates
    logger.info("Monitoring events for 2 minutes...")

    for i in range(8):  # 8 x 15 seconds = 2 minutes
        await asyncio.sleep(15)

        # Status update
        if last_event_time:
            seconds_since = (datetime.now() - last_event_time).total_seconds()
            logger.info(
                f"Status @ {(i+1)*15}s: {event_count} events received "
                f"(last: {seconds_since:.0f}s ago)"
            )
        else:
            logger.info(f"Status @ {(i+1)*15}s: No events received yet")

        # Manual data check every 30 seconds
        if (i + 1) % 2 == 0:
            try:
                data = await suite.data.get_data("15sec", bars=1)
                if data is not None and len(data) > 0:
                    logger.debug(
                        f"Manual poll: 15sec close={data.tail(1)['close'][0]:.2f}"
                    )
            except Exception as e:
                logger.error(f"Manual poll error: {e}")

    logger.info(f"Final: {event_count} total events received")

    # Cleanup
    await suite.disconnect()
    logger.info("Disconnected")


if __name__ == "__main__":
    asyncio.run(main())
