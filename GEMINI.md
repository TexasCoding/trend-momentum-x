# GEMINI.md

This file provides guidance to Google's Gemini models when working with code in this repository.

# TrendMomentumX Trading Strategy

## Project Overview
This is a multi-timeframe trend-aligned momentum breakout strategy for futures trading, primarily targeting ES (E-mini S&P 500 Futures). The strategy uses project_x_py as the sole source of trading functionality.

## Strategy Core Principles
- **Primary Timeframe**: 15-second bars for entry/exit signals
- **Trend Verification**: 1-minute, 5-minute, and 15-minute timeframes for trend alignment
- **Expected Frequency**: 5-15 trades per day per instrument
- **Risk Management**: 1:2 risk-reward ratio minimum, 0.5-1% risk per trade
- **Operating Hours**: 24/5 (Sunday 6 PM ET to Friday 5 PM ET for CME futures)

## Architecture

### Module Structure
```
trend-momentum-x/
├── main.py                 # Main entry point - TrendMomentumXStrategy class
├── strategy/               # Core strategy components (all async)
│   ├── __init__.py        # Exports: TrendAnalyzer, SignalGenerator, OrderBookAnalyzer, RiskManager, ExitManager
│   ├── trend_analysis.py   # Multi-timeframe trend determination
│   ├── signals.py          # Entry signal generation (RSI, WAE, patterns)
│   ├── orderbook.py        # Level 2 data analysis and confirmation
│   ├── risk_manager.py     # Position sizing and risk management
│   └── exits.py            # Exit rules and trailing stop logic
├── indicators/            # Custom indicators (NOT YET IMPLEMENTED)
│   ├── wae.py             # Waddah Attar Explosion indicator
│   ├── patterns.py        # Fair Value Gaps and Order Blocks
│   └── fusion.py          # Custom indicator combinations
├── backtest/              # Backtesting framework (NOT YET IMPLEMENTED)
│   └── engine.py          # Backtesting engine
├── utils/                 # Utilities
│   ├── __init__.py        # Exports: Config, setup_logger
│   ├── config.py          # Configuration management with environment variables
│   └── logger.py          # Async logging setup
└── tests/                 # Test suite
    ├── conftest.py        # Pytest fixtures and mocks
    └── test_*.py          # Test files for each module
```

## Key Components

### 1. Trend Determination (Multi-Timeframe)
- **15-minute**: 50 & 200 EMA for primary trend
- **5-minute**: MACD histogram for momentum confirmation
- **1-minute**: WAE for fine-tuned momentum check
- All timeframes must align for trade entry

### 2. Entry Signals (15-second)
**Long Entry Requirements:**
- RSI(14) crosses above 40 after dipping below 30
- WAE explosion above sensitivity threshold
- Price bounces from Bullish Order Block or fills FVG upward
- Price breaks above previous 15s high

**Short Entry Requirements:**
- RSI(14) crosses below 60 after rising above 70
- WAE explosion with negative trend line
- Price rejects from Bearish Order Block or fills FVG downward
- Price breaks below previous 15s low

### 3. Level 2 Confirmation
- Bid-Ask Imbalance thresholds: >1.5 for longs, <0.67 for shorts
- Iceberg order detection for hidden liquidity
- 5-10 second scan window before entry

### 4. Exit Rules
- Initial target: 2x risk (dynamic via ATR)
- Stop loss: 1% or 10-15 ticks (whichever tighter)
- Trailing stop: Parabolic SAR after 1x risk achieved
- Time exit: Close after 5 minutes without progress
- Trend reversal: Exit if higher timeframe flips

## Implementation Guidelines

### project_x_py Integration Notes
- Use `TradingSuite.create()` with orderbook=True, risk_manager=True
- The TradingSuite handles WebSocket subscriptions internally
- All strategy components accept TradingSuite instance in constructor
- Use async/await pattern for all data fetching and order operations
- Polars DataFrames are returned from all data operations

### Critical Functions to Implement
1. `calculate_multi_timeframe_trend()` - Returns trend state across all timeframes
2. `detect_entry_signal()` - Combines RSI, WAE, and pattern detection
3. `confirm_with_orderbook()` - Validates signal with Level 2 data
4. `calculate_position_size()` - Risk-based position sizing
5. `manage_exits()` - Handles all exit conditions

### Development Workflow for Gemini
1.  **Understand the Goal**: Clarify the user's request before writing code.
2.  **Locate Relevant Files**: Use the architecture guide and file search to find the right files to modify.
3.  **Read Before Modifying**: Always read the contents of a file and its corresponding test file before making changes.
4.  **Write or Modify Code**: Apply the requested changes, adhering strictly to the existing coding style, patterns, and `project-x-py` API.
5.  **Run Quality Checks**: After any modification, run `uv run ruff check --fix && uv run ruff format && uv run mypy .` to ensure code quality.
6.  **Run Tests**: Run `uv run pytest` to ensure all changes are covered by tests and that no regressions were introduced.
7.  **Commit Changes**: Once all checks pass, prepare a descriptive commit message.

## Package Management

This project uses `uv`. Use `uv run ...` to execute commands within the project's virtual environment.

```bash
# Install or update dependencies from pyproject.toml
uv sync

# Add a new dependency
uv add <package-name>
```

## Development Commands

### Code Quality
```bash
# Run ruff linter and auto-fix
uv run ruff check --fix

# Format code with ruff
uv run ruff format

# Run type checking with mypy
uv run mypy .

# Run all checks (linting + type checking)
uv run ruff check && uv run mypy .
```

### Testing
```bash
# Run all unit and integration tests
uv run pytest

# Run tests with coverage report
uv run pytest --cov=strategy --cov-report=html

# Run a specific test file
uv run pytest tests/test_trend_analysis.py

# Run tests with verbose output
uv run pytest -v

# Run only unit tests (exclude integration)
uv run pytest -m "not integration"

# Run integration tests only
uv run pytest -m integration
```

### Running the Strategy
```bash
# Paper trading mode (default)
uv run python main.py

# Live trading mode (use with extreme caution)
TRADING_MODE=live uv run python main.py
```

## project-x-py API Reference

### TradingSuite
Main interface for all trading operations.

```python
from project_x_py import TradingSuite

# Create suite with all features
suite = await TradingSuite.create(
    instrument="ES",
    orderbook=True,
    risk_manager=True,
    data_feeds=["15s", "1min", "5min", "15min"]
)
```

### Data Manager
Access historical and real-time data.

```python
# Get historical data
data = await suite.data.get_data("15s", bars=100)  # Returns polars DataFrame
```

### OrderBook Analysis
Level 2 market data analysis.

```python
# Get market imbalance
imbalance = await suite.orderbook.get_market_imbalance(levels=5)
```

### Order Management
Place and manage orders.

```python
# Place bracket order
response = await suite.orders.place_bracket_order(
    contract_id=str(suite.instrument.id),
    side=0,  # 0=long, 1=short
    size=1,
    entry_price=4500.00,
    stop_loss_price=4495.00,
    take_profit_price=4510.00
)
```

### Indicators
Technical indicators optimized for polars DataFrames.

```python
from project_x_py.indicators import RSI, MACD, EMA, ATR, SAR, WAE, FVG, ORDERBLOCK

# Apply indicators using pipe method
data = (data
    .pipe(RSI, period=14)
    .pipe(WAE, sensitivity=150)
)
```

## Known Issues and TODOs

### Current Implementation Status
1. **Core Modules**: All strategy modules are implemented with comprehensive test coverage (91%).
2. **Indicators Directory**: NOT IMPLEMENTED. The strategy uses indicators directly from `project-x-py`.
3. **Backtesting**: NOT IMPLEMENTED. Only paper/live trading is available.

### TODO List
- [ ] Implement custom indicators in `indicators/` directory.
- [ ] Implement backtesting framework in `backtest/` directory.
- [ ] Implement order status tracking and fill confirmation.
- [ ] Add performance metrics tracking and reporting.

## Configuration

### Environment Variables
- `INSTRUMENT`: e.g., `ES`
- `TRADING_MODE`: `paper` or `live`
- `RISK_PER_TRADE`: e.g., `0.005` (0.5%)
- `MAX_DAILY_LOSS`: e.g., `0.03` (3%)
- `RSI_PERIOD`: e.g., `14`
- `WAE_SENSITIVITY`: e.g., `150`
- `IMBALANCE_LONG_THRESHOLD`: e.g., `1.5`
- `TIME_EXIT_MINUTES`: e.g., `5`