"""Unit tests for the signals module."""

from unittest.mock import AsyncMock

import polars as pl
import pytest

from strategy.signals import SignalGenerator


class TestSignalGenerator:
    """Test suite for SignalGenerator class."""

    @pytest.mark.asyncio
    async def test_initialization(self, mock_suite):
        """Test SignalGenerator initialization."""
        generator = SignalGenerator(mock_suite)
        assert generator.suite == mock_suite
        assert generator.rsi_period == 14
        assert generator.rsi_oversold == 30
        assert generator.rsi_overbought == 70

    @pytest.mark.asyncio
    async def test_check_long_entry_no_data(self, mock_suite):
        """Test long entry check with no data."""
        mock_suite.data.get_data.return_value = None

        generator = SignalGenerator(mock_suite)
        valid, signals = await generator.check_long_entry()

        assert valid is False
        assert signals["rsi_cross"] is False
        assert signals["wae_explosion"] is False

    @pytest.mark.asyncio
    async def test_check_long_entry_insufficient_data(self, mock_suite):
        """Test long entry check with insufficient data."""
        # Create data with less than required bars
        small_data = pl.DataFrame({
            "close": [5000.0, 5001.0],
            "high": [5002.0, 5003.0],
            "low": [4999.0, 5000.0],
            "volume": [100, 150]
        })
        mock_suite.data.get_data.return_value = small_data

        generator = SignalGenerator(mock_suite)
        valid, signals = await generator.check_long_entry()

        assert valid is False

    @pytest.mark.asyncio
    async def test_check_long_entry_valid_signal(self, mock_suite, sample_ohlcv_data):
        """Test long entry with valid signal conditions."""
        from project_x_py.indicators import RSI, WAE

        # Prepare data with indicators
        data = sample_ohlcv_data.pipe(RSI, period=14).pipe(WAE, sensitivity=150)

        # Mock bullish pattern check
        generator = SignalGenerator(mock_suite)
        generator._check_bullish_pattern = AsyncMock(return_value=True)

        # Set up bullish conditions
        data = data.with_columns([
            pl.Series("RSI_14", [25.0] * (len(data) - 2) + [28.0, 45.0]),  # Cross from oversold
            pl.Series("WAE_explosion", [0.0] * (len(data) - 1) + [200.0]),  # Strong explosion
            pl.Series("WAE_trend", [0.0] * (len(data) - 1) + [1.0]),  # Positive trend
            pl.Series("WAE_deadzone", [0.0] * (len(data) - 1) + [100.0])  # Below explosion
        ])

        mock_suite.data.get_data.return_value = data

        valid, signals = await generator.check_long_entry()

        # Check individual signal components
        assert signals["rsi_cross"] is True
        assert signals["wae_explosion"] is True
        assert signals["price_break"] is True
        assert signals["pattern_edge"] is True
        assert valid is True

    @pytest.mark.asyncio
    async def test_check_short_entry_valid_signal(self, mock_suite, sample_ohlcv_data):
        """Test short entry with valid signal conditions."""
        from project_x_py.indicators import RSI, WAE

        # Prepare data with indicators
        data = sample_ohlcv_data.pipe(RSI, period=14).pipe(WAE, sensitivity=150)

        # Mock bearish pattern check
        generator = SignalGenerator(mock_suite)
        generator._check_bearish_pattern = AsyncMock(return_value=True)

        # Set up bearish conditions
        data = data.with_columns([
            pl.Series("RSI_14", [75.0] * (len(data) - 2) + [72.0, 55.0]),  # Cross from overbought
            pl.Series("WAE_explosion", [0.0] * (len(data) - 1) + [200.0]),  # Strong explosion
            pl.Series("WAE_trend", [0.0] * (len(data) - 1) + [-1.0]),  # Negative trend
            pl.Series("WAE_deadzone", [0.0] * (len(data) - 1) + [100.0])  # Below explosion
        ])

        mock_suite.data.get_data.return_value = data

        valid, signals = await generator.check_short_entry()

        assert signals["rsi_cross"] is True
        assert signals["wae_explosion"] is True
        assert valid is True

    @pytest.mark.asyncio
    async def test_check_bullish_pattern(self, mock_suite):
        """Test bullish pattern detection."""
        import polars as pl
        from project_x_py.indicators import FVG, ORDERBLOCK
        
        # Create 5-minute data with required columns
        data_5m = pl.DataFrame({
            "timestamp": pl.datetime_range(
                start=pl.datetime(2024, 1, 1, 9, 0),
                end=pl.datetime(2024, 1, 1, 9, 20),
                interval="5m",
                eager=True
            ),
            "open": [5000.0 + i for i in range(5)],
            "high": [5002.0 + i for i in range(5)],
            "low": [4998.0 + i for i in range(5)],
            "close": [5001.0 + i for i in range(5)],
            "volume": [1000 + i * 100 for i in range(5)]
        })
        
        # Apply indicators and mock the results
        data_5m = data_5m.with_columns([
            pl.lit("bullish").alias("ORDERBLOCK_type"),
            pl.lit(4995.0).alias("ORDERBLOCK_low"),
            pl.lit("neutral").alias("FVG_type")
        ])

        # Mock 15-second data with current price above order block
        data_15s = pl.DataFrame({
            "close": [5000.0]  # Above order block low
        })

        mock_suite.data.get_data.side_effect = [data_5m, data_15s]

        generator = SignalGenerator(mock_suite)
        result = await generator._check_bullish_pattern()

        assert result is True

    @pytest.mark.asyncio
    async def test_check_bearish_pattern(self, mock_suite):
        """Test bearish pattern detection."""
        import polars as pl
        
        # Create 5-minute data with required columns  
        data_5m = pl.DataFrame({
            "timestamp": pl.datetime_range(
                start=pl.datetime(2024, 1, 1, 9, 0),
                end=pl.datetime(2024, 1, 1, 9, 20),
                interval="5m",
                eager=True
            ),
            "open": [5000.0 + i for i in range(5)],
            "high": [5002.0 + i for i in range(5)],
            "low": [4998.0 + i for i in range(5)],
            "close": [5001.0 + i for i in range(5)],
            "volume": [1000 + i * 100 for i in range(5)]
        })
        
        # Apply indicators and mock the results
        data_5m = data_5m.with_columns([
            pl.lit("bearish").alias("ORDERBLOCK_type"),
            pl.lit(5005.0).alias("ORDERBLOCK_high"),
            pl.lit("neutral").alias("FVG_type")
        ])

        # Mock 15-second data with current price below order block
        data_15s = pl.DataFrame({
            "close": [5000.0]  # Below order block high
        })

        mock_suite.data.get_data.side_effect = [data_5m, data_15s]

        generator = SignalGenerator(mock_suite)
        result = await generator._check_bearish_pattern()

        assert result is True

    @pytest.mark.asyncio
    async def test_get_microstructure_score(self, mock_suite, sample_ohlcv_data):
        """Test microstructure score calculation."""
        from project_x_py.indicators import RSI, WAE

        # Prepare data with indicators
        data = sample_ohlcv_data.pipe(RSI, period=14).pipe(WAE, sensitivity=150)

        # Add specific RSI and WAE values
        data = data.with_columns([
            pl.Series("RSI_14", list(range(30, 30 + len(data)))),
            pl.Series("WAE_explosion", [150.0] * len(data))
        ])

        mock_suite.data.get_data.return_value = data

        generator = SignalGenerator(mock_suite)
        score = await generator.get_microstructure_score()

        assert isinstance(score, float)
        assert score >= 0.0

    @pytest.mark.asyncio
    async def test_signal_details_structure(self, mock_suite, sample_ohlcv_data):
        """Test that signal details have correct structure."""
        from project_x_py.indicators import RSI, WAE

        data = sample_ohlcv_data.pipe(RSI, period=14).pipe(WAE, sensitivity=150)
        mock_suite.data.get_data.return_value = data

        generator = SignalGenerator(mock_suite)
        generator._check_bullish_pattern = AsyncMock(return_value=False)

        _, signals = await generator.check_long_entry()

        assert "details" in signals
        assert "rsi" in signals["details"]
        assert "wae" in signals["details"]
        assert "price" in signals["details"]
        assert "prev" in signals["details"]["rsi"]
        assert "current" in signals["details"]["rsi"]