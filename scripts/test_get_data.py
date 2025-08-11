#!/usr/bin/env python3
"""Test the get_data method to ensure we're using it correctly."""

import asyncio
import logging

from project_x_py import TradingSuite

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


async def main():
    """Test get_data method."""
    logger.info("Testing get_data method...")

    # Create suite
    suite = await TradingSuite.create(
        instrument="MES",
        timeframes=["15sec", "1min", "5min", "15min"],
        initial_days=5,
        features=["orderbook", "risk_manager"],
    )

    logger.info("Suite created, testing get_data...")

    # Test 1: Basic get_data call
    logger.info("\n1. Testing basic get_data call for 15sec:")
    try:
        data = await suite.data.get_data("15sec", bars=10)
        if data is not None:
            logger.info(f"   Success! Got {len(data)} bars")
            logger.info(f"   Columns: {data.columns}")
            logger.info(f"   Last bar: {data.tail(1)}")
        else:
            logger.warning("   Got None from get_data")
    except Exception as e:
        logger.error(f"   Error: {e}")

    # Test 2: Try different timeframes
    logger.info("\n2. Testing all timeframes:")
    for tf in ["15sec", "1min", "5min", "15min"]:
        try:
            data = await suite.data.get_data(tf)  # No bars parameter
            if data is not None:
                logger.info(f"   {tf}: Got {len(data)} bars (default)")
            else:
                logger.warning(f"   {tf}: Got None")
        except Exception as e:
            logger.error(f"   {tf}: Error - {e}")

    # Test 3: Check what parameters get_data accepts
    logger.info("\n3. Testing different parameter combinations:")

    # Try with bars parameter
    try:
        data = await suite.data.get_data("1min", bars=5)
        logger.info(f"   get_data('1min', bars=5): Success - {len(data) if data else 0} bars")
    except Exception as e:
        logger.error(f"   get_data('1min', bars=5): Error - {e}")

    # Try without bars parameter
    try:
        data = await suite.data.get_data("1min")
        logger.info(f"   get_data('1min'): Success - {len(data) if data else 0} bars")
    except Exception as e:
        logger.error(f"   get_data('1min'): Error - {e}")

    # Test 4: Check if we need to use a different method
    logger.info("\n4. Checking data manager methods:")
    logger.info(f"   Available methods: {[m for m in dir(suite.data) if not m.startswith('_')]}")

    # Test 5: Try getting current price
    logger.info("\n5. Testing get_current_price:")
    try:
        price = await suite.data.get_current_price()
        logger.info(f"   Current price: {price}")
    except Exception as e:
        logger.error(f"   Error getting current price: {e}")

    # Test 6: Subscribe to events and then try get_data
    logger.info("\n6. Testing get_data after event subscription:")

    event_received = asyncio.Event()

    async def on_new_bar(event):
        logger.info("   Received NEW_BAR event")
        event_received.set()
        # Try get_data from within event handler
        try:
            data = await suite.data.get_data("15sec", bars=1)
            logger.info(f"   get_data from event handler: Success - {len(data) if data else 0} bars")
        except Exception as e:
            logger.error(f"   get_data from event handler: Error - {e}")

    from project_x_py import EventType
    await suite.on(EventType.NEW_BAR, on_new_bar)

    # Wait for an event
    try:
        await asyncio.wait_for(event_received.wait(), timeout=20)
    except TimeoutError:
        logger.warning("   No event received in 20 seconds")

    # Try get_data after event
    try:
        data = await suite.data.get_data("15sec", bars=1)
        logger.info(f"   get_data after event: Success - {len(data) if data else 0} bars")
    except Exception as e:
        logger.error(f"   get_data after event: Error - {e}")

    await suite.disconnect()
    logger.info("\nTest complete!")


if __name__ == "__main__":
    asyncio.run(main())
