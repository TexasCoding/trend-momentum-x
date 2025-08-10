# PROJECT-X-PY API REFERENCE AND SOURCE GUIDE

## CRITICAL: This is the authoritative reference for project-x-py usage in TrendMomentumX

### Source Code Location
The project-x-py library is installed at:
- **Main Path**: `.venv/lib/python3.12/site-packages/project_x_py/`
- **Version Info**: `.venv/lib/python3.12/site-packages/project_x_py-3.1.3.dist-info/`

### Official Documentation
- **Documentation URL**: https://texascoding.github.io/project-x-py/
- **GitHub Repository**: https://github.com/TexasCoding/project-x-py

## Core Import Pattern
```python
# ALWAYS use this import pattern - DO NOT import individual modules
from project_x_py import TradingSuite

# The TradingSuite is the ONLY entry point to all functionality
# IMPORTANT: Use 'features' parameter as a list of strings, NOT individual boolean flags
suite = await TradingSuite.create(
    instrument="ES",
    timeframes=["15sec", "1min", "5min", "15min"],  # Optional, defaults to ["5min"]
    features=["orderbook", "risk_manager"],  # List of feature strings
    initial_days=5,  # Days of historical data to load
    auto_connect=True  # Auto-initialize components
)
```

## Source Code Structure
```
project_x_py/
├── __init__.py                 # Main exports (TradingSuite, indicators, etc.)
├── trading_suite.py            # Core TradingSuite class - ALL functionality accessed through this
├── config.py                   # Configuration management
├── models.py                   # Data models and structures
├── event_bus.py               # Event handling system
├── exceptions.py              # Custom exceptions
├── order_templates.py         # Order templates and builders
├── order_tracker.py           # Order tracking system
├── client/                    # API client implementation
│   ├── auth.py               # Authentication
│   ├── base.py               # Base client
│   └── tradovate.py         # Tradovate-specific implementation
├── indicators/                # Technical indicators (ALL optimized for polars)
│   ├── __init__.py           # Exports all indicators
│   ├── base.py               # Base indicator class
│   ├── momentum.py           # RSI, MACD, Stochastic
│   ├── overlap.py            # EMA, SMA, Bollinger Bands
│   ├── volatility.py         # ATR, SAR
│   ├── waddah_attar.py       # Waddah Attar Explosion
│   ├── fvg.py                # Fair Value Gaps
│   └── order_block.py        # Order Blocks
├── order_manager/            # Order management
│   ├── __init__.py
│   ├── core.py              # Core order operations
│   └── operations.py        # Order execution
├── orderbook/                # Level 2 data analysis
│   ├── __init__.py
│   ├── base.py              # OrderBookBase class
│   ├── analytics.py         # Market analytics
│   ├── detection.py         # Iceberg/cluster detection
│   ├── profile.py           # Volume profile
│   └── realtime.py          # Real-time handling
├── position_manager/         # Position management
│   ├── __init__.py
│   ├── core.py              # Position operations
│   ├── risk.py              # Risk calculations
│   └── tracking.py          # Position tracking
├── realtime_data_manager/    # Real-time data handling
│   ├── __init__.py
│   ├── core.py              # RealtimeDataManager class
│   ├── data_access.py       # Data retrieval methods
│   ├── data_processing.py   # Data processing
│   └── callbacks.py         # Callback handling
├── risk_manager/             # Risk management
│   ├── __init__.py
│   └── manager.py           # Risk calculations
├── types/                    # Type definitions
│   ├── __init__.py
│   ├── base.py              # Base types
│   ├── trading.py           # Trading types
│   ├── market_data.py       # Market data types
│   └── response_types.py    # API response types
└── utils/                    # Utilities
    ├── __init__.py
    ├── logging.py           # Logging utilities
    └── helpers.py           # Helper functions
```

## Key API Components and Their Source Files

### 1. TradingSuite (trading_suite.py)
The main interface - ALWAYS access functionality through this:
```python
# Access patterns - NEVER access modules directly
suite.data           # RealtimeDataManager - data operations
suite.orders         # OrderManager - order operations  
suite.orderbook      # OrderBookAnalyzer - Level 2 data
suite.risk_manager   # RiskManager - risk calculations
suite.instrument     # Instrument info (Contract object)
suite.client         # API client (rarely needed directly)
```

### 2. Data Operations (realtime_data_manager/)
```python
# Get historical data - returns polars DataFrame or None
data = await suite.data.get_data("15sec", bars=100)

# DataFrame columns:
# - timestamp: Bar timestamp (timezone-aware datetime)
# - open: Opening price
# - high: High price
# - low: Low price  
# - close: Close price
# - volume: Volume

# Get current price
price = await suite.data.get_current_price()  # Returns float or None

# Get multi-timeframe data
mtf_data = await suite.data.get_mtf_data()  # Returns dict[str, pl.DataFrame]

# Subscribe to updates (handled internally)
# DO NOT manually subscribe - TradingSuite handles this
```

### 3. OrderBook Analysis (orderbook/)
```python
# Market imbalance - returns LiquidityAnalysisResponse
imbalance = await suite.orderbook.get_market_imbalance(levels=5)
# Response fields:
# - depth_imbalance: float (buy/sell pressure ratio)
# - bid_depth: dict with volume and level count
# - ask_depth: dict with volume and level count
# - analysis: str (text description)

# Iceberg detection - returns dict
icebergs = await suite.orderbook.detect_iceberg_orders(
    min_refreshes=3,
    volume_threshold=100,
    time_window_minutes=30
)
# Response: {'iceberg_levels': [...], 'timestamp': ...}

# OrderBook snapshot - returns dict
snapshot = await suite.orderbook.get_orderbook_snapshot(levels=10)
# Response: {
#     'bids': [{'price': float, 'size': int}, ...],
#     'asks': [{'price': float, 'size': int}, ...],
#     'best_bid': float,
#     'best_ask': float,
#     'spread': float
# }
```

### 4. Order Management (order_manager/)
```python
# Place bracket order
response = await suite.orders.place_bracket_order(
    contract_id=str(suite.instrument.id),
    side=0,  # 0=long, 1=short (from project_x_py.types)
    size=1,
    entry_price=4500.00,
    stop_loss_price=4495.00,
    take_profit_price=4510.00
)

# Modify order
await suite.orders.modify_order(order_id, stop_loss_price=new_stop)

# Close position
await suite.orders.close_position(position_id)
```

### 5. Technical Indicators (indicators/)
ALL indicators are in project_x_py.indicators and work with polars DataFrames:
```python
from project_x_py.indicators import (
    RSI, MACD, EMA, SMA, ATR, SAR,
    WAE, FVG, ORDERBLOCK, VWAP, 
    BollingerBands, Stochastic
)

# Apply using pipe method - ALWAYS use this pattern
data = (data
    .pipe(RSI, period=14)
    .pipe(MACD, fast_period=12, slow_period=26, signal_period=9)
    .pipe(EMA, period=50, column_name="EMA_50")
    .pipe(WAE, sensitivity=150)
    .pipe(FVG, min_gap_size=0.001)
    .pipe(ORDERBLOCK, min_volume_percentile=70)
)

# Access values
rsi = data["RSI_14"].tail(1)[0]
macd_hist = data["MACD_histogram"].tail(1)[0]
```

## Critical Type Definitions (types/)

### Side Enum (types/trading.py)
```python
# ALWAYS use these values for order side
LONG = 0
SHORT = 1
```

### Response Types (types/response_types.py)
```python
# OrderResponse - returned from order operations
# LiquidityAnalysisResponse - from orderbook analysis
# MarketDataResponse - from data operations
```

## Common Mistakes to AVOID

### ❌ WRONG - Direct module imports
```python
# NEVER DO THIS
from project_x_py.indicators import RSI
from project_x_py.order_manager import OrderManager
from project_x_py.realtime_data_manager import RealtimeDataManager
```

### ✅ CORRECT - Use TradingSuite
```python
# ALWAYS DO THIS
from project_x_py import TradingSuite
suite = await TradingSuite.create(...)
data = await suite.data.get_data(...)
```

### ❌ WRONG - Manual WebSocket handling
```python
# NEVER manually handle WebSockets
ws = WebSocketClient(...)
await ws.connect()
```

### ✅ CORRECT - Let TradingSuite handle it
```python
# TradingSuite handles all WebSocket connections internally
suite = await TradingSuite.create(...)
# WebSocket is already connected and managed
```

### ❌ WRONG - Creating custom indicators
```python
# DON'T recreate indicators that exist in project_x_py
def calculate_rsi(data, period=14):
    # Custom implementation
```

### ✅ CORRECT - Use project_x_py indicators
```python
from project_x_py.indicators import RSI
data = data.pipe(RSI, period=14)
```

## Validation Checklist

When reviewing code, ensure:
1. ✓ All imports come from `project_x_py` package
2. ✓ TradingSuite is the only entry point
3. ✓ No direct module imports (except indicators for pipe)
4. ✓ All data operations use polars DataFrames
5. ✓ Indicators applied using `.pipe()` method
6. ✓ Async/await used for all suite operations
7. ✓ No manual WebSocket handling
8. ✓ Order side uses 0 (long) or 1 (short)
9. ✓ No custom implementations of existing indicators

## Example: Correct Full Implementation
```python
from project_x_py import TradingSuite
from project_x_py.indicators import RSI, MACD, EMA, WAE, FVG, ORDERBLOCK
import polars as pl

class TrendMomentumXStrategy:
    def __init__(self):
        self.suite = None
    
    async def initialize(self):
        # Create suite - single entry point
        self.suite = await TradingSuite.create(
            instrument="ES",
            features=["orderbook", "risk_manager"],
            timeframes=["15sec", "1min", "5min", "15min"]
        )
    
    async def get_signals(self):
        # Get data through suite
        data = await self.suite.data.get_data("15sec", bars=100)
        
        # Apply indicators using pipe
        data = (data
            .pipe(RSI, period=14)
            .pipe(MACD)
            .pipe(WAE, sensitivity=150)
            .pipe(FVG, min_gap_size=0.001)
            .pipe(ORDERBLOCK, min_volume_percentile=70)
        )
        
        # Get orderbook data through suite
        imbalance = await self.suite.orderbook.get_market_imbalance(levels=5)
        
        # Place order through suite
        if self.should_enter_long(data, imbalance):
            response = await self.suite.orders.place_bracket_order(
                contract_id=str(self.suite.instrument.id),
                side=0,  # Long
                size=1,
                entry_price=entry,
                stop_loss_price=stop,
                take_profit_price=target
            )
        
        return data
```

## How to Find Information

### 1. Check Source Code
```bash
# View specific module
cat .venv/lib/python3.12/site-packages/project_x_py/trading_suite.py

# Search for specific functionality
grep -r "place_bracket_order" .venv/lib/python3.12/site-packages/project_x_py/

# List available indicators
ls .venv/lib/python3.12/site-packages/project_x_py/indicators/
```

### 2. Check Documentation
- Main docs: https://texascoding.github.io/project-x-py/
- API Reference: https://texascoding.github.io/project-x-py/api/
- Examples: Check project_x_py GitHub repository

### 3. Check Type Hints
```python
# Use Python's help system
from project_x_py import TradingSuite
help(TradingSuite.create)

# Check method signatures
suite = await TradingSuite.create(...)
help(suite.orders.place_bracket_order)
```

## IMPORTANT RULES FOR AI AGENTS

1. **ALWAYS reference this file first** when implementing any trading functionality
2. **NEVER guess API methods** - check the source code at `.venv/lib/python3.12/site-packages/project_x_py/`
3. **ALWAYS use TradingSuite** as the entry point - never import modules directly
4. **VERIFY method signatures** by checking the actual source files
5. **USE project_x_py indicators** - don't reimplement existing functionality
6. **FOLLOW the patterns** shown in this reference exactly

## Quick Reference Paths

- **Main Entry**: `.venv/lib/python3.12/site-packages/project_x_py/__init__.py`
- **TradingSuite**: `.venv/lib/python3.12/site-packages/project_x_py/trading_suite.py`
- **Indicators**: `.venv/lib/python3.12/site-packages/project_x_py/indicators/`
- **Types**: `.venv/lib/python3.12/site-packages/project_x_py/types/`
- **OrderBook**: `.venv/lib/python3.12/site-packages/project_x_py/orderbook/`
- **Examples**: Search GitHub - https://github.com/TexasCoding/project-x-py/tree/main/examples

This reference is the single source of truth for project-x-py usage in this project.