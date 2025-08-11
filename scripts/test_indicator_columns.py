#!/usr/bin/env python3
"""Test to check what column names indicators create."""

import asyncio
import logging

from project_x_py import TradingSuite
from project_x_py.indicators import ATR, EMA, MACD, RSI, SAR, WAE

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """Test indicator column names."""
    logger.info("Testing indicator column names...")

    suite = await TradingSuite.create(
        instrument="MES",
        timeframes=["15min"],
        initial_days=5,
    )

    logger.info("Getting data and applying indicators...")

    # Get 15min data
    data = await suite.data.get_data("15min", bars=200)
    logger.info(f"Original columns: {data.columns}")

    # Apply EMA
    data_with_ema = data.pipe(EMA, period=50)
    logger.info(f"After EMA(50): {data_with_ema.columns}")

    # Apply both EMAs
    data_with_both = (data
                      .pipe(EMA, period=50)
                      .pipe(EMA, period=200))
    logger.info(f"After EMA(50) and EMA(200): {data_with_both.columns}")

    # Check the actual values
    last_row = data_with_both.tail(1)
    logger.info(f"Last row columns: {last_row.columns}")
    for col in last_row.columns:
        if "ema" in col.lower() or "EMA" in col:
            logger.info(f"  {col}: {last_row[col][0]}")

    # Test MACD
    data_with_macd = data.pipe(MACD)
    logger.info(f"After MACD: {data_with_macd.columns}")

    # Test RSI
    data_with_rsi = data.pipe(RSI, period=14)
    logger.info(f"After RSI(14): {data_with_rsi.columns}")

    # Test WAE
    data_with_wae = data.pipe(WAE, sensitivity=150)
    logger.info(f"After WAE: {data_with_wae.columns}")

    # Test ATR
    data_with_atr = data.pipe(ATR, period=14)
    logger.info(f"After ATR(14): {data_with_atr.columns}")

    # Test SAR
    data_with_sar = data.pipe(SAR)
    logger.info(f"After SAR: {data_with_sar.columns}")

    await suite.disconnect()
    logger.info("Done!")


if __name__ == "__main__":
    asyncio.run(main())
