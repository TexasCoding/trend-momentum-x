#!/usr/bin/env python3
"""Test to monitor ALL events from project-x-py."""

import asyncio
import logging
from datetime import datetime
from typing import Any

from project_x_py import EventType, TradingSuite

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Suppress debug logs from project-x-py internals
logging.getLogger("project_x_py.realtime.core").setLevel(logging.WARNING)
logging.getLogger("project_x_py.orderbook").setLevel(logging.WARNING)


async def main():
    """Test all events."""
    logger.info("Starting comprehensive event test...")

    # Create suite with MES like your strategy
    suite = await TradingSuite.create(
        instrument="MES",
        timeframes=["15sec", "1min", "5min", "15min"],
        initial_days=5,
        features=["orderbook"],
    )

    logger.info("TradingSuite created")

    # Track events
    event_counts = {}
    last_event_times = {}

    async def event_handler(event_type: str):
        """Generic event handler."""
        async def handler(event: Any) -> None:
            now = datetime.now()
            event_counts[event_type] = event_counts.get(event_type, 0) + 1
            last_event_times[event_type] = now

            # Log the event with details
            data = getattr(event, "data", {})
            if event_type == "NEW_BAR":
                timeframe = data.get("timeframe", "unknown")
                bar_data = data.get("data", {})
                logger.info(f"📊 {event_type} - {timeframe}: Close={bar_data.get('close', 0)}, Volume={bar_data.get('volume', 0)}")
            elif event_counts[event_type] <= 5:  # Only log first 5 of other types
                logger.info(f"📨 {event_type} event #{event_counts[event_type]}")
        return handler

    # Register handlers for all event types
    event_types = [
        EventType.NEW_BAR,
        EventType.DATA_UPDATE,
        EventType.QUOTE_UPDATE,
        EventType.TRADE_TICK,
        EventType.ORDERBOOK_UPDATE,
        EventType.MARKET_DEPTH_UPDATE,
    ]

    for event_type in event_types:
        await suite.on(event_type, await event_handler(event_type.value))

    logger.info(f"Registered handlers for {len(event_types)} event types")

    # Run for 2 minutes
    logger.info("Monitoring events for 2 minutes...")

    # Print status every 30 seconds
    for i in range(4):
        await asyncio.sleep(30)
        logger.info("=" * 50)
        logger.info(f"Event summary after {(i+1)*30} seconds:")
        for event_type, count in sorted(event_counts.items()):
            last_time = last_event_times.get(event_type)
            if last_time:
                seconds_ago = (datetime.now() - last_time).total_seconds()
                logger.info(f"  {event_type}: {count} events (last: {seconds_ago:.0f}s ago)")
            else:
                logger.info(f"  {event_type}: {count} events")

        # Check if NEW_BAR events have stopped
        if "new_bar" in event_counts and "new_bar" in last_event_times:
            seconds_since = (datetime.now() - last_event_times["new_bar"]).total_seconds()
            if seconds_since > 60:
                logger.warning(f"⚠️ NEW_BAR events stopped {seconds_since:.0f}s ago!")

    logger.info("=" * 50)
    logger.info("Final event counts:")
    for event_type, count in sorted(event_counts.items()):
        logger.info(f"  {event_type}: {count} total events")

    # Cleanup
    await suite.disconnect()
    logger.info("Disconnected")


if __name__ == "__main__":
    asyncio.run(main())
