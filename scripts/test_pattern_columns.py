#!/usr/bin/env python3
"""Test to verify FVG and ORDERBLOCK column names."""

import asyncio
import logging

from project_x_py import TradingSuite
from project_x_py.indicators import FVG, ORDERBLOCK

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """Test FVG and ORDERBLOCK column names."""
    logger.info("Testing FVG and ORDERBLOCK column names...")

    suite = await TradingSuite.create(
        instrument="MES",
        timeframes=["5min"],
        initial_days=5,
    )

    logger.info("Getting data and applying indicators...")

    # Get 5min data
    data = await suite.data.get_data("5min", bars=200)
    logger.info(f"Original columns: {data.columns}")

    # Apply FVG
    data_with_fvg = data.pipe(FVG, min_gap_size=0.001, check_mitigation=True)
    fvg_columns = [col for col in data_with_fvg.columns if 'fvg' in col.lower() or 'FVG' in col]
    logger.info(f"FVG columns added: {fvg_columns}")

    # Apply ORDERBLOCK
    data_with_ob = data.pipe(ORDERBLOCK, min_volume_percentile=70)
    ob_columns = [col for col in data_with_ob.columns if 'ob' in col.lower() or 'ORDERBLOCK' in col or 'order' in col.lower()]
    logger.info(f"ORDERBLOCK columns added: {ob_columns}")

    # Apply both
    data_with_both = (data
                      .pipe(FVG, min_gap_size=0.001, check_mitigation=True)
                      .pipe(ORDERBLOCK, min_volume_percentile=70))

    logger.info("\nAll columns after applying both indicators:")
    for col in data_with_both.columns:
        if 'fvg' in col.lower() or 'ob' in col.lower() or 'order' in col.lower():
            logger.info(f"  - {col}")

    # Check last row values
    last_row = data_with_both.tail(1)
    logger.info("\nLast row pattern-related values:")
    for col in last_row.columns:
        if 'fvg' in col.lower() or 'ob' in col.lower() or 'order' in col.lower():
            value = last_row[col][0]
            logger.info(f"  {col}: {value}")

    await suite.disconnect()
    logger.info("Done!")


if __name__ == "__main__":
    asyncio.run(main())
