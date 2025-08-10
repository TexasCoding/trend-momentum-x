# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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

### Testing Commands
```bash
# Run all unit tests
uv run pytest

# Run unit tests with coverage
uv run pytest --cov=strategy --cov-report=html

# Run specific test file
uv run pytest tests/test_trend_analysis.py

# Run tests with verbose output
uv run pytest -v

# Run only unit tests (exclude integration)
uv run pytest -m "not integration"

# Run integration tests only
uv run pytest -m integration
```

### Performance Metrics to Track
- Win rate (target: >55%)
- Risk-reward ratio (minimum: 1:2)
- Sharpe ratio (target: >1.5)
- Max drawdown (limit: 5% weekly)
- Average trade duration
- Slippage and commission impact

## Development Notes

### Priority Order
1. Implement and test trend determination logic
2. Build entry signal detection with standard indicators
3. Add custom patterns (FVG, Order Blocks)
4. Integrate Level 2 OrderBook analysis
5. Implement risk management and exits
6. Build backtesting framework
7. Add real-time WebSocket integration
8. Thoroughly test in paper mode before live

### Key Considerations
- Volume filter: Ignore signals when 15s volume < 20% of 1m average
- Correlation filter: Avoid concurrent ES and NQ trades if correlation > 0.8
- Connection handling: Implement reconnection logic for 24/5 operation
- Logging: Comprehensive async logging for all trades and decisions

### project_x_py Examples to Reference
- `06_multi_timeframe_strategy.py` - Multi-timeframe handling
- `07_technical_indicators.py` - Indicator fusion
- `05_orderbook_analysis.py` - Level 2 data analysis
- `12_simplified_strategy.py` - Streamlined execution

## Risk Warnings
- This is a high-frequency strategy requiring low-latency infrastructure
- Backtested results do not guarantee future performance
- Always test thoroughly in paper mode before live trading
- Monitor for market regime changes that may invalidate strategy assumptions

## Package Management

### Package Manager: uv
This project uses `uv` as the package manager for fast, reliable Python dependency management.

```bash
# Install dependencies
uv sync

# Run commands within the virtual environment
uv run python main.py
uv run ruff check
uv run mypy .

# Add new dependencies
uv add package-name

# Update dependencies
uv sync --upgrade
```

### Core Dependencies
- **project-x-py**: Main trading framework providing all trading functionality
- **polars**: High-performance DataFrame library for data processing
- **Python 3.12+**: Required for modern type hints and performance improvements

## Development Commands

### Code Quality
```bash
# Validate project-x-py API usage (ALWAYS RUN THIS FIRST)
uv run python validate_api_usage.py

# Run ruff linter
uv run ruff check

# Run ruff with auto-fix
uv run ruff check --fix

# Format code with ruff
uv run ruff format

# Run type checking with mypy
uv run mypy .

# Run all checks (API validation + linting + type checking)
uv run python validate_api_usage.py && uv run ruff check && uv run mypy .
```

### Testing
```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=strategy --cov-report=html

# Run specific test file
uv run pytest tests/test_trend_analysis.py

# Run with verbose output
uv run pytest -v
```

### Running the Strategy
```bash
# Paper trading mode (default)
uv run python main.py

# Live trading mode (use with extreme caution)
TRADING_MODE=live uv run python main.py

# With custom configuration
INSTRUMENT=NQ RISK_PER_TRADE=0.01 uv run python main.py

# NOTE: The strategy currently has no backtesting capability.
# The backtest/ directory structure exists but is not implemented.
# Live or paper trading is the only way to test the strategy.
```

## project-x-py API Reference

### CRITICAL SOURCE LOCATIONS
**ALWAYS reference these paths for accurate API usage:**
- **Source Code**: `.venv/lib/python3.12/site-packages/project_x_py/`
- **Main Reference**: `PROJECT_X_PY_REFERENCE.md` (authoritative API guide)
- **Documentation**: https://texascoding.github.io/project-x-py/
- **Version Info**: `.venv/lib/python3.12/site-packages/project_x_py-3.1.1.dist-info/`

**When implementing ANY trading functionality:**
1. First check `PROJECT_X_PY_REFERENCE.md` for patterns
2. Verify actual implementation in source at `.venv/lib/python3.12/site-packages/project_x_py/`
3. Never guess API methods - always verify in source code

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

# Get current price
price = await suite.data.get_current_price()

# Subscribe to real-time updates (handled internally by TradingSuite)
```

### OrderBook Analysis
Level 2 market data analysis.

```python
# Get market imbalance
imbalance = await suite.orderbook.get_market_imbalance(levels=5)
# Returns: LiquidityAnalysisResponse with depth_imbalance field

# Detect iceberg orders
icebergs = await suite.orderbook.detect_iceberg_orders()
# Returns: dict with 'iceberg_levels' key

# Get orderbook snapshot
snapshot = await suite.orderbook.get_orderbook_snapshot(levels=10)
# Returns: dict with 'bids' and 'asks' arrays
```

### Order Management
Place and manage orders.

```python
# Place bracket order (entry + stop loss + take profit)
response = await suite.orders.place_bracket_order(
    contract_id=str(suite.instrument.id),
    side=0,  # 0=long, 1=short
    size=1,
    entry_price=4500.00,
    stop_loss_price=4495.00,
    take_profit_price=4510.00
)

# Modify existing order
await suite.orders.modify_order(order_id, stop_loss_price=new_stop)

# Close position
await suite.orders.close_position(position_id)
```

### Indicators
Technical indicators optimized for polars DataFrames.

```python
from project_x_py.indicators import RSI, MACD, EMA, ATR, SAR, WAE, FVG, ORDERBLOCK

# Apply indicators using pipe method
data = (data
    .pipe(RSI, period=14)
    .pipe(MACD)
    .pipe(EMA, period=50)
    .pipe(WAE, sensitivity=150)
    .pipe(FVG, min_gap_size=0.001)
    .pipe(ORDERBLOCK, min_volume_percentile=70)
)

# Access indicator values
rsi_value = data["RSI_14"].tail(1)[0]
macd_histogram = data["MACD_histogram"].tail(1)[0]
```

### Instrument Properties
Access instrument specifications.

```python
instrument = suite.instrument
tick_size = instrument.tickSize  # Minimum price movement
tick_value = instrument.tickValue  # Dollar value per tick
contract_id = instrument.id  # Unique identifier
```

### Account Information
Get account details.

```python
account = suite.client.get_account_info()
balance = account.balance  # Account balance
margin = account.margin  # Available margin
```

## Known Issues and TODOs

### Current Implementation Status
1. **Core Modules**: All strategy modules (trend_analysis, signals, orderbook, risk_manager, exits) have been implemented with comprehensive test coverage
2. **Indicators Directory**: Structure exists but custom indicators (WAE, FVG, OrderBlock) are NOT implemented - using project-x-py indicators instead
3. **Backtesting**: Directory structure exists but NOT implemented - only paper/live trading available
4. **Event Handling**: WebSocket event subscription is handled internally by TradingSuite, callback mechanism needs verification
5. **Order Management**: Basic order placement implemented, but order status tracking and fill confirmation needs work

### TODO List
- [x] Add comprehensive unit tests for all strategy modules (91% test coverage achieved)
- [ ] Implement custom indicators in indicators/ directory (WAE, FVG, OrderBlock)
- [ ] Implement backtesting framework in backtest/ directory
- [ ] Implement order status tracking and fill confirmation
- [ ] Add performance metrics tracking and reporting
- [ ] Create dashboard for real-time monitoring
- [ ] Add more sophisticated correlation analysis between instruments
- [ ] Implement adaptive position sizing based on volatility
- [ ] Add market regime detection (trending vs ranging)
- [ ] Implement emergency shutdown procedures
- [ ] Add Telegram/Discord notifications for trades
- [ ] Create configuration file system (YAML/JSON)
- [ ] Add database logging for trade history
- [ ] Implement strategy parameter optimization framework

### Future Enhancements
1. **Machine Learning Integration**: Add ML-based signal filtering
2. **Multi-Instrument Support**: Extend to trade multiple futures simultaneously
3. **Options Integration**: Add options strategies for hedging
4. **Advanced Risk Management**: Kelly criterion position sizing
5. **Market Microstructure**: Add more sophisticated order flow analysis

## Troubleshooting

### Common Issues

**Issue**: "OrderBook data unavailable"
- Solution: Ensure TradingSuite is created with `orderbook=True`
- Check that the data feed is connected and receiving updates

**Issue**: DataFrame operations failing
- Solution: Always check if data is not None and has sufficient length
- Use `.tail()` and `.select()` methods for safe data access

**Issue**: Type checking errors with Python 3.12
- Solution: Use `|` instead of `Union` for type hints
- Example: `str | None` instead of `Optional[str]`

**Issue**: Async operations blocking
- Solution: Ensure all data fetching uses `await`
- Use `asyncio.create_task()` for concurrent operations

## Configuration

### Environment Variables
```bash
# Trading configuration
INSTRUMENT=ES               # Instrument to trade
TRADING_MODE=paper          # paper or live
RISK_PER_TRADE=0.005       # Risk per trade (0.5%)
MAX_DAILY_LOSS=0.03        # Max daily loss (3%)
MAX_WEEKLY_LOSS=0.05       # Max weekly loss (5%)
MAX_CONCURRENT_TRADES=3    # Max positions at once

# Technical parameters
RSI_PERIOD=14
RSI_OVERSOLD=30
RSI_OVERBOUGHT=70
WAE_SENSITIVITY=150
VOLUME_THRESHOLD_PERCENT=0.2

# OrderBook parameters
IMBALANCE_LONG_THRESHOLD=1.5
IMBALANCE_SHORT_THRESHOLD=0.6667
ORDERBOOK_DEPTH_LEVELS=5

# Exit management
TIME_EXIT_MINUTES=5
BREAKEVEN_TRIGGER_RATIO=1.0
TRAILING_STOP_ENABLED=true
```

### Logging Configuration
The strategy uses Python's standard logging with async support. Logs are written to:
- Console: INFO level and above
- File: `logs/trading_{date}.log` - DEBUG level and above

## Testing Strategy

### Test Coverage
The project has comprehensive test coverage (91%) with both unit and integration tests:
- **Unit Tests**: Test individual components in isolation using mocks
- **Integration Tests**: Test component interactions with mocked TradingSuite
- **Fixtures**: Shared test data and mocks in `tests/conftest.py`

### Running Tests
```bash
# Quick test run during development
uv run pytest tests/test_trend_analysis.py -v

# Full test suite before commits
uv run pytest --cov=strategy

# Check specific functionality
uv run pytest -k "test_long_entry" -v
```

## Key Architecture Patterns

### Async/Await Pattern
All strategy components use async methods for non-blocking operations:
```python
# All data fetching is async
data = await suite.data.get_data("15s", bars=100)

# All strategy methods that fetch data are async
trend = await trend_analyzer.calculate_multi_timeframe_trend()
signal = await signal_generator.detect_entry_signal()
```

### Dependency Injection
All strategy components receive TradingSuite in constructor:
```python
class TrendAnalyzer:
    def __init__(self, suite: TradingSuite):
        self.suite = suite
```

### Configuration Management
- All configuration comes from environment variables via `Config` class
- No hardcoded values in strategy logic
- Config provides typed access to all settings

## Contact and Support

For issues with:
- **project-x-py**: Check documentation at https://texascoding.github.io/project-x-py/
- **Strategy Logic**: Review examples in project-x-py repository
- **Development**: Follow the testing commands and start with paper trading