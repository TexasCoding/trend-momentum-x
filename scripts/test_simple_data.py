#!/usr/bin/env python3
"""Simple test to check if data fetching works."""

import asyncio
import logging

from project_x_py import TradingSuite

from utils import Config

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


async def main():
    """Test data fetching."""
    logger.info("Creating TradingSuite...")

    suite = await TradingSuite.create(
        instrument=Config.INSTRUMENT,
        timeframes=Config.TIMEFRAMES,
        initial_days=5,
        features=["orderbook", "risk_manager"],
    )

    logger.info("Suite created, testing data fetches...")

    # Test each timeframe
    for tf in ["15sec", "1min", "5min", "15min"]:
        try:
            logger.info(f"Fetching {tf} data...")
            data = await asyncio.wait_for(
                suite.data.get_data(tf, bars=10),
                timeout=5.0
            )
            if data is not None:
                logger.info(f"  {tf}: Got {len(data)} bars")
            else:
                logger.warning(f"  {tf}: No data")
        except TimeoutError:
            logger.error(f"  {tf}: TIMEOUT!")
        except Exception as e:
            logger.error(f"  {tf}: ERROR - {e}")

    # Test multiple quick fetches
    logger.info("\nTesting rapid fetches...")
    for i in range(5):
        try:
            logger.info(f"Fetch #{i+1}...")
            data = await asyncio.wait_for(
                suite.data.get_data("15sec", bars=1),
                timeout=2.0
            )
            logger.info(f"  Success - got {len(data) if data else 0} bars")
        except TimeoutError:
            logger.error(f"  Fetch #{i+1} TIMEOUT!")
        except Exception as e:
            logger.error(f"  Fetch #{i+1} ERROR - {e}")

    await suite.disconnect()
    logger.info("Done")


if __name__ == "__main__":
    asyncio.run(main())
