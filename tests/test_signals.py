"""Unit tests for the signals module."""

from unittest.mock import AsyncMock, patch

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
    async def test_check_long_entry_valid_signal(self, mock_suite):
        """Test long entry with valid signal conditions."""
        # Create larger dataset for indicators
        data = pl.DataFrame({
            "timestamp": pl.datetime_range(
                start=pl.datetime(2024, 1, 1, 9, 0),
                end=pl.datetime(2024, 1, 1, 9, 30),
                interval="15s",
                eager=True
            ),
            "open": [5000.0 + i * 0.1 for i in range(121)],
            "high": [5002.0 + i * 0.1 for i in range(121)],
            "low": [4999.0 + i * 0.1 for i in range(121)],
            "close": [5001.0 + i * 0.1 for i in range(121)],
            "volume": [100 + i for i in range(121)]
        })

        # Mock bullish pattern check
        generator = SignalGenerator(mock_suite)
        with patch.object(generator, '_check_bullish_pattern', new_callable=AsyncMock) as mock_pattern:
            mock_pattern.return_value = True

            # Set up bullish conditions - manually add indicator columns
            # The last 20 rows will be used by the strategy
            rsi_values = [35.0] * 100 + [25.0] * 19 + [45.0, 45.0]  # Cross from oversold (121 total)
            wae_explosion = [0.0] * 119 + [200.0, 200.0]  # Strong explosion
            wae_trend = [0.0] * 119 + [1.0, 1.0]  # Positive trend
            wae_deadzone = [100.0] * 121  # Deadzone threshold
            
            data = data.with_columns([
                pl.Series("RSI_14", rsi_values[:len(data)]),
                pl.Series("WAE_explosion", wae_explosion[:len(data)]),
                pl.Series("WAE_trend", wae_trend[:len(data)]),
                pl.Series("WAE_deadzone", wae_deadzone[:len(data)])
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
    async def test_check_short_entry_valid_signal(self, mock_suite):
        """Test short entry with valid signal conditions."""
        # Create larger dataset
        data = pl.DataFrame({
            "timestamp": pl.datetime_range(
                start=pl.datetime(2024, 1, 1, 9, 0),
                end=pl.datetime(2024, 1, 1, 9, 30),
                interval="15s",
                eager=True
            ),
            "open": [5010.0 - i * 0.1 for i in range(121)],
            "high": [5012.0 - i * 0.1 for i in range(121)],
            "low": [5009.0 - i * 0.1 for i in range(121)],
            "close": [5011.0 - i * 0.1 for i in range(121)],
            "volume": [100 + i for i in range(121)]
        })

        # Mock bearish pattern check
        generator = SignalGenerator(mock_suite)
        with patch.object(generator, '_check_bearish_pattern', new_callable=AsyncMock) as mock_pattern:
            mock_pattern.return_value = True

            # Set up bearish conditions
            rsi_values = [65.0] * 100 + [75.0] * 19 + [55.0, 55.0]  # Cross from overbought (121 total)
            wae_explosion = [0.0] * 119 + [200.0, 200.0]  # Strong explosion
            wae_trend = [0.0] * 119 + [-1.0, -1.0]  # Negative trend
            wae_deadzone = [100.0] * 121  # Deadzone threshold
            
            data = data.with_columns([
                pl.Series("RSI_14", rsi_values[:len(data)]),
                pl.Series("WAE_explosion", wae_explosion[:len(data)]),
                pl.Series("WAE_trend", wae_trend[:len(data)]),
                pl.Series("WAE_deadzone", wae_deadzone[:len(data)])
            ])

            mock_suite.data.get_data.return_value = data

            valid, signals = await generator.check_short_entry()

            assert signals["rsi_cross"] is True
            assert signals["wae_explosion"] is True
            assert valid is True

    @pytest.mark.asyncio
    async def test_check_bullish_pattern(self, mock_suite):
        """Test bullish pattern detection."""
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
    async def test_get_microstructure_score(self, mock_suite):
        """Test microstructure score calculation."""
        # Create larger dataset
        data = pl.DataFrame({
            "timestamp": pl.datetime_range(
                start=pl.datetime(2024, 1, 1, 9, 0),
                end=pl.datetime(2024, 1, 1, 9, 30),
                interval="15s",
                eager=True
            ),
            "open": [5000.0 + i * 0.1 for i in range(121)],
            "high": [5002.0 + i * 0.1 for i in range(121)],
            "low": [4999.0 + i * 0.1 for i in range(121)],
            "close": [5001.0 + i * 0.1 for i in range(121)],
            "volume": [100 + i for i in range(121)]
        })

        # Add RSI and WAE columns manually
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
    async def test_signal_details_structure(self, mock_suite):
        """Test that signal details have correct structure."""
        # Create larger dataset
        data = pl.DataFrame({
            "timestamp": pl.datetime_range(
                start=pl.datetime(2024, 1, 1, 9, 0),
                end=pl.datetime(2024, 1, 1, 9, 30),
                interval="15s",
                eager=True
            ),
            "open": [5000.0 + i * 0.1 for i in range(121)],
            "high": [5002.0 + i * 0.1 for i in range(121)],
            "low": [4999.0 + i * 0.1 for i in range(121)],
            "close": [5001.0 + i * 0.1 for i in range(121)],
            "volume": [100 + i for i in range(121)]
        })

        # Add required indicator columns
        data = data.with_columns([
            pl.Series("RSI_14", [50.0] * len(data)),
            pl.Series("WAE_explosion", [100.0] * len(data)),
            pl.Series("WAE_trend", [0.0] * len(data)),
            pl.Series("WAE_deadzone", [150.0] * len(data))
        ])

        mock_suite.data.get_data.return_value = data

        generator = SignalGenerator(mock_suite)
        with patch.object(generator, '_check_bullish_pattern', new_callable=AsyncMock) as mock_pattern:
            mock_pattern.return_value = False

            _, signals = await generator.check_long_entry()

            assert "details" in signals
            assert "rsi" in signals["details"]
            assert "wae" in signals["details"]
            assert "price" in signals["details"]
            assert "prev" in signals["details"]["rsi"]
            assert "current" in signals["details"]["rsi"]