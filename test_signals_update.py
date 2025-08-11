#!/usr/bin/env python3
"""Test the updated signal logic to ensure less restrictive requirements."""

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock

from strategy.signals import SignalGenerator
from utils import Config

# Setup logging
logging.basicConfig(level=logging.DEBUG, format='%(message)s')


async def test_signal_requirements():
    """Test that signals now work with 3/4 requirements."""
    # Mock TradingSuite
    suite = MagicMock()
    suite.data = AsyncMock()
    
    # Create signal generator
    generator = SignalGenerator(suite)
    
    # Check configuration
    print(f"Min signals required: {generator.min_signals_required}")
    print(f"Pattern required: {generator.pattern_required}")
    print(f"RSI oversold threshold: {generator.rsi_oversold}")
    print(f"RSI overbought threshold: {generator.rsi_overbought}")
    print(f"RSI lookback bars: {generator.rsi_lookback}")
    print(f"Weights: RSI={generator.weight_rsi}, WAE={generator.weight_wae}, Price={generator.weight_price}, Pattern={generator.weight_pattern}")
    
    # Verify configuration values
    assert generator.min_signals_required == 3, f"Expected 3, got {generator.min_signals_required}"
    assert generator.pattern_required == False, f"Expected False, got {generator.pattern_required}"
    assert generator.rsi_oversold == 35, f"Expected 35, got {generator.rsi_oversold}"
    assert generator.rsi_overbought == 65, f"Expected 65, got {generator.rsi_overbought}"
    assert generator.rsi_lookback == 20, f"Expected 20, got {generator.rsi_lookback}"
    
    print("\n✅ All configuration checks passed!")
    print("\nKey changes implemented:")
    print("1. Reduced signal requirement from 4/4 to 3/4")
    print("2. Made pattern detection optional (bonus points if found)")
    print("3. Relaxed RSI thresholds (30->35 oversold, 70->65 overbought)")
    print("4. Increased RSI lookback from 10 to 20 bars")
    print("5. Added weighted signal scoring system")
    print("\nThe strategy should now generate more trading signals!")


if __name__ == "__main__":
    asyncio.run(test_signal_requirements())