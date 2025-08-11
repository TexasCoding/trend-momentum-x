#!/usr/bin/env python3
"""Test OrderBook API to verify method names and return types."""

import asyncio
import os

from project_x_py import TradingSuite

# Set environment variables for testing
os.environ["PROJECT_X_API_KEY"] = os.getenv("PROJECT_X_API_KEY", "test")
os.environ["PROJECT_X_API_URL"] = os.getenv("PROJECT_X_API_URL", "https://api.tradovate.com")

async def test_orderbook_api():
    """Test OrderBook API methods and return types."""
    print("Testing OrderBook API...")

    try:
        # Create suite with orderbook feature
        suite = await TradingSuite.create(
            instrument="MES",
            features=["orderbook"],
            timeframes=["1min"],
            initial_days=1
        )

        print("\n1. Testing get_market_imbalance()...")
        try:
            result = await suite.orderbook.get_market_imbalance(levels=5)
            print(f"   Type: {type(result)}")
            print(f"   Keys: {list(result.keys()) if isinstance(result, dict) else 'Not a dict'}")
            if isinstance(result, dict):
                for key, value in result.items():
                    print(f"   - {key}: {value} (type: {type(value).__name__})")
        except Exception as e:
            print(f"   Error: {e}")

        print("\n2. Testing detect_iceberg_orders()...")
        try:
            result = await suite.orderbook.detect_iceberg_orders()
            print(f"   Type: {type(result)}")
            if isinstance(result, dict):
                print(f"   Keys: {list(result.keys())}")
                for key, value in result.items():
                    if key == "iceberg_levels":
                        print(f"   - {key}: {type(value).__name__} with {len(value) if hasattr(value, '__len__') else 0} items")
                    else:
                        print(f"   - {key}: {value}")
        except Exception as e:
            print(f"   Error: {e}")

        print("\n3. Testing get_orderbook_snapshot()...")
        try:
            result = await suite.orderbook.get_orderbook_snapshot(levels=10)
            print(f"   Type: {type(result)}")
            if isinstance(result, dict):
                print(f"   Keys: {list(result.keys())}")
                for key, value in result.items():
                    if key in ["bids", "asks"]:
                        print(f"   - {key}: {type(value).__name__} with {len(value) if hasattr(value, '__len__') else 0} levels")
                        if value and len(value) > 0:
                            print(f"     Sample: {value[0] if isinstance(value, list) else 'N/A'}")
                    else:
                        print(f"   - {key}: {value}")
        except Exception as e:
            print(f"   Error: {e}")

        print("\n4. Checking if suite.orderbook exists...")
        print(f"   hasattr(suite, 'orderbook'): {hasattr(suite, 'orderbook')}")
        print(f"   suite.orderbook is None: {suite.orderbook is None}")
        if hasattr(suite, 'orderbook') and suite.orderbook:
            print(f"   suite.orderbook type: {type(suite.orderbook)}")
            print(f"   Methods available: {[m for m in dir(suite.orderbook) if not m.startswith('_')]}")

        await suite.disconnect()
        print("\nTest complete!")

    except Exception as e:
        print(f"Failed to create TradingSuite: {e}")
        print("\nNote: This test requires valid PROJECT_X_API_KEY environment variable")


if __name__ == "__main__":
    asyncio.run(test_orderbook_api())
