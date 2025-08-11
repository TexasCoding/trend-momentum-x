#!/usr/bin/env python3
"""Test to monitor NEW_BAR events with detailed timeframe logging."""

import asyncio
import logging
from datetime import datetime
from typing import Any

from project_x_py import EventType, TradingSuite

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Suppress debug logs from project-x-py internals
logging.getLogger("project_x_py").setLevel(logging.WARNING)


async def main():
    """Test NEW_BAR events specifically."""
    logger.info("Starting NEW_BAR event test...")

    # Create suite with MES like your strategy
    suite = await TradingSuite.create(
        instrument="MES",
        timeframes=["15sec", "1min", "5min", "15min"],
        initial_days=5,
        features=["orderbook"],
    )

    logger.info("TradingSuite created")

    # Track events by timeframe
    timeframe_counts = {}
    timeframe_last_time = {}

    async def new_bar_handler(event: Any) -> None:
        """Handle NEW_BAR events with detailed logging."""
        try:
            now = datetime.now()

            # Extract data from event
            data = getattr(event, "data", {})
            timeframe = data.get("timeframe", "unknown")
            bar_data = data.get("data", {})

            # Update counts
            timeframe_counts[timeframe] = timeframe_counts.get(timeframe, 0) + 1

            # Calculate time since last event
            time_since_last = "first"
            if timeframe in timeframe_last_time:
                seconds_since = (now - timeframe_last_time[timeframe]).total_seconds()
                time_since_last = f"{seconds_since:.1f}s"

            timeframe_last_time[timeframe] = now

            # Log the event
            logger.info(
                f"📊 NEW_BAR [{timeframe:>6s}] #{timeframe_counts[timeframe]:3d} | "
                f"Gap: {time_since_last:>6s} | "
                f"Close: {bar_data.get('close', 0):>8.2f} | "
                f"Volume: {bar_data.get('volume', 0):>6d} | "
                f"Time: {bar_data.get('timestamp', 'N/A')}"
            )

        except Exception as e:
            logger.error(f"Error in handler: {e}")

    # Register handler
    await suite.on(EventType.NEW_BAR, new_bar_handler)
    logger.info("Handler registered for NEW_BAR events")

    # Also manually check data periodically
    async def manual_data_check():
        """Manually check for new data."""
        while True:
            await asyncio.sleep(15)  # Check every 15 seconds
            try:
                data = await suite.data.get_data("15sec", bars=2)
                if data is not None and len(data) > 0:
                    last_bar = data.tail(1)
                    logger.info(
                        f"🔍 MANUAL CHECK [15sec]: "
                        f"Close={last_bar['close'][0]:.2f} "
                        f"Volume={last_bar['volume'][0]} "
                        f"Time={last_bar['timestamp'][0] if 'timestamp' in last_bar.columns else 'N/A'}"
                    )
            except Exception as e:
                logger.error(f"Manual check error: {e}")

    # Start manual check task
    check_task = asyncio.create_task(manual_data_check())

    # Run for 3 minutes
    logger.info("Monitoring events for 3 minutes...")

    # Print status every 30 seconds
    for i in range(6):
        await asyncio.sleep(30)
        logger.info("=" * 60)
        logger.info(f"Summary after {(i+1)*30} seconds:")

        for tf in ["15sec", "1min", "5min", "15min"]:
            count = timeframe_counts.get(tf, 0)
            if count > 0:
                last_time = timeframe_last_time.get(tf)
                if last_time:
                    seconds_ago = (datetime.now() - last_time).total_seconds()
                    logger.info(f"  {tf:>6s}: {count:3d} events (last: {seconds_ago:>6.1f}s ago)")
                else:
                    logger.info(f"  {tf:>6s}: {count:3d} events")
            else:
                logger.info(f"  {tf:>6s}: No events received")

        # Check for stalled 15sec events
        if "15sec" in timeframe_last_time:
            seconds_since = (datetime.now() - timeframe_last_time["15sec"]).total_seconds()
            if seconds_since > 30:
                logger.warning(f"⚠️  15sec events appear stalled ({seconds_since:.0f}s since last)")

    logger.info("=" * 60)
    logger.info("Final summary:")
    for tf, count in sorted(timeframe_counts.items()):
        logger.info(f"  {tf}: {count} total events")

    # Cancel manual check task
    check_task.cancel()
    try:
        await check_task
    except asyncio.CancelledError:
        pass

    # Cleanup
    await suite.disconnect()
    logger.info("Disconnected")


if __name__ == "__main__":
    asyncio.run(main())
