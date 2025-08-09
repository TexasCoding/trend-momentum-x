# TrendMomentumX Trading Strategy

A multi-timeframe trend-aligned momentum breakout strategy for futures trading, powered by [Project X](https://www.projectx.com/) and built with [project-x-py](https://github.com/TexasCoding/project-x-py).

## Overview

TrendMomentumX is a sophisticated algorithmic trading strategy that combines multi-timeframe analysis with momentum indicators and order book confirmation. Built exclusively on the Project X trading framework through its Python SDK ([project-x-py](https://texascoding.github.io/project-x-py/)), this strategy is designed for futures trading with a focus on ES (E-mini S&P 500) and NQ (Nasdaq-100) contracts.

## Features

- **Multi-Timeframe Analysis**: 15-second base timeframe with 1-minute, 5-minute, and 15-minute trend verification
- **Advanced Signal Generation**: RSI, Waddah Attar Explosion (WAE), Fair Value Gaps (FVG), and Order Blocks
- **Level 2 OrderBook Confirmation**: Real-time bid-ask imbalance analysis and iceberg order detection
- **Risk Management**: Dynamic position sizing, stop-loss, take-profit, and trailing stops using Parabolic SAR
- **24/5 Operation**: Designed for continuous futures market operation with robust error handling
- **Modern Python**: Built with Python 3.12+ using async/await patterns and type hints

## Project X Integration

This strategy leverages the full power of [Project X](https://www.projectx.com/), a comprehensive trading framework that provides:
- Real-time WebSocket data feeds
- Level 2 order book analysis
- Advanced technical indicators optimized with Polars DataFrames
- Unified order management system
- Risk management tools

All trading functionality is provided through [project-x-py](https://github.com/TexasCoding/project-x-py), the official Python SDK for Project X.

## Installation

### Prerequisites

- Python 3.12 or higher
- [uv](https://github.com/astral-sh/uv) package manager (recommended)

### Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/trend-momentum-x.git
cd trend-momentum-x
```

2. Install dependencies using uv:
```bash
uv sync
```

Or with pip:
```bash
pip install -r requirements.txt
```

## Configuration

### Environment Variables

Create a `.env` file in the project root or set environment variables:

```bash
# Project X Authentication
PROJECT_X_API_KEY=your_api_key
PROJECT_X_API_SECRET=your_api_secret

# Trading Configuration
INSTRUMENT=ES                    # Trading instrument (ES, NQ, etc.)
TRADING_MODE=paper               # paper or live
RISK_PER_TRADE=0.005            # 0.5% risk per trade
MAX_DAILY_LOSS=0.03             # 3% daily loss limit
MAX_WEEKLY_LOSS=0.05            # 5% weekly loss limit
MAX_CONCURRENT_TRADES=3         # Maximum concurrent positions

# Technical Parameters
RSI_PERIOD=14
RSI_OVERSOLD=30
RSI_OVERBOUGHT=70
WAE_SENSITIVITY=150
VOLUME_THRESHOLD_PERCENT=0.2

# OrderBook Parameters
IMBALANCE_LONG_THRESHOLD=1.5
IMBALANCE_SHORT_THRESHOLD=0.6667
ORDERBOOK_DEPTH_LEVELS=5
```

## Usage

### Development Commands

```bash
# Run linting
uv run ruff check

# Run type checking
uv run mypy .

# Format code
uv run ruff format
```

### Running the Strategy

#### Paper Trading (Recommended First)
```bash
uv run python main.py
```

#### Live Trading (Use with Caution)
```bash
TRADING_MODE=live uv run python main.py
```

#### Custom Configuration
```bash
INSTRUMENT=NQ RISK_PER_TRADE=0.01 uv run python main.py
```

## Strategy Logic

### Entry Conditions

**Long Entry Requirements:**
1. All timeframes aligned bullish (15m, 5m, 1m)
2. RSI(14) crosses above 40 after dipping below 30
3. WAE explosion above sensitivity threshold with positive trend
4. Price bounces from Bullish Order Block or fills Fair Value Gap upward
5. OrderBook bid-ask imbalance > 1.5
6. No iceberg orders detected on ask side

**Short Entry Requirements:**
1. All timeframes aligned bearish (15m, 5m, 1m)
2. RSI(14) crosses below 60 after rising above 70
3. WAE explosion with negative trend line
4. Price rejects from Bearish Order Block or fills Fair Value Gap downward
5. OrderBook bid-ask imbalance < 0.67
6. No iceberg orders detected on bid side

### Exit Management

- **Initial Target**: 2x risk (dynamically calculated via ATR)
- **Stop Loss**: 1% or 10-15 ticks (whichever is tighter)
- **Trailing Stop**: Parabolic SAR activated after 1x risk achieved
- **Time Exit**: Close position after 5 minutes without progress
- **Trend Reversal**: Exit if higher timeframe trend flips

## Project Structure

```
trend-momentum-x/
├── main.py                 # Main entry point and trading loop
├── strategy/               # Strategy components
│   ├── __init__.py
│   ├── trend_analysis.py   # Multi-timeframe trend determination
│   ├── signals.py          # Entry signal generation
│   ├── orderbook.py        # Level 2 OrderBook analysis
│   ├── risk_manager.py     # Position sizing and risk management
│   └── exits.py            # Exit rules and trailing stops
├── utils/                  # Utilities
│   ├── __init__.py
│   ├── config.py          # Configuration management
│   └── logger.py          # Logging setup
├── CLAUDE.md              # Comprehensive development documentation
├── pyproject.toml         # Project configuration and dependencies
└── uv.lock               # Locked dependencies
```

## Safety Features

1. **Volume Filter**: Ignores signals in thin markets (volume < 20% of 1-minute average)
2. **Risk Limits**: Automatically stops trading at daily/weekly loss limits
3. **Position Limits**: Enforces maximum concurrent positions
4. **Correlation Filter**: Prevents correlated trades (e.g., ES and NQ when correlation > 0.8)
5. **Graceful Shutdown**: Closes all positions and saves state on exit

## Monitoring

The strategy provides comprehensive logging:
- **Console**: INFO level and above for real-time monitoring
- **File**: `logs/trading_YYYYMMDD.log` with DEBUG level for detailed analysis

Key metrics tracked:
- Daily and weekly P&L
- Win rate and risk-reward ratio
- Average trade duration
- Number of trades per session
- Slippage and commission impact

## Testing Recommendations

1. **Paper Trading**: Test for at least 2-4 weeks on a paper account
2. **Small Size**: Start with minimum position sizes when going live
3. **Monitor Closely**: Watch the first 100 trades carefully
4. **Parameter Tuning**: Adjust parameters based on market conditions
5. **Market Conditions**: Test in different volatility regimes

## Documentation

- [CLAUDE.md](CLAUDE.md) - Comprehensive development documentation
- [Project X Documentation](https://texascoding.github.io/project-x-py/) - Official project-x-py documentation
- [Project X GitHub](https://github.com/TexasCoding/project-x) - Main Project X repository

## Contributing

Contributions are welcome! Please ensure:
1. Code passes all linting checks (`uv run ruff check`)
2. Type hints are properly added (`uv run mypy .`)
3. New features are documented
4. Tests are added for new functionality

## Support

For issues related to:
- **project-x-py**: Check the [official documentation](https://texascoding.github.io/project-x-py/)
- **Project X**: Visit the [Project X repository](https://github.com/TexasCoding/project-x)
- **Strategy Logic**: Open an issue in this repository

## Disclaimer

**IMPORTANT**: This strategy is for educational purposes only. Trading futures involves substantial risk of loss and is not suitable for all investors. Past performance is not indicative of future results. 

- Always test thoroughly on paper accounts before live trading
- Never risk more than you can afford to lose
- Consider consulting with a financial advisor
- Be aware that market conditions can change rapidly

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Built with [Project X](https://www.projectx.com/) - The comprehensive trading framework
- Powered by [project-x-py](https://github.com/TexasCoding/project-x-py) - The official Python SDK
- Optimized with [Polars](https://github.com/pola-rs/polars) - Lightning-fast DataFrame library
- Package management by [uv](https://github.com/astral-sh/uv) - An extremely fast Python package installer