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
        assert generator.wae_sensitivity == 150
        assert generator.pattern_required is True
        assert generator.weight_pattern == 2.0

    @pytest.mark.asyncio
    async def test_check_long_entry_no_data(self, mock_suite):
        """Test long entry check with no data."""
        mock_suite.data.get_data.return_value = None

        generator = SignalGenerator(mock_suite)
        valid, signals = await generator.check_long_entry()

        assert valid is False
        assert signals["wae_explosion"] is False
        assert signals["pattern_edge"] is False

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
    async def test_check_long_entry_with_all_signals(self, mock_suite, sample_15s_data):
        """Test long entry with all signals present including pattern."""
        # Modify data to trigger signals
        data = sample_15s_data.with_columns([
            pl.lit(40.0).alias("wae_explosion"),
            pl.lit(1.0).alias("wae_trend"),
            pl.lit(20.0).alias("wae_dead_zone"),
        ])
        
        # Set up for price break (current close > prev high)
        # Make the second-to-last high lower than the last close
        data = data.with_columns([
            pl.when(pl.arange(len(data)) == len(data) - 2)
            .then(5000.0)  # Set prev high lower
            .otherwise(pl.col("high"))
            .alias("high"),
            pl.when(pl.arange(len(data)) == len(data) - 1)
            .then(5010.0)  # Set current close higher
            .otherwise(pl.col("close"))
            .alias("close")
        ])
        
        mock_suite.data.get_data.return_value = data
        
        generator = SignalGenerator(mock_suite)
        
        # Mock pattern check to return True
        with patch.object(generator, '_check_bullish_pattern', return_value=True):
            valid, signals = await generator.check_long_entry()
        
        assert valid is True
        assert signals["wae_explosion"] is True
        assert signals["price_break"] is True
        assert signals["pattern_edge"] is True
        assert signals["signals_met"] == 3  # pattern + 2 other signals

    @pytest.mark.asyncio
    async def test_check_long_entry_without_pattern(self, mock_suite, sample_15s_data):
        """Test long entry fails without pattern even with other signals."""
        # Modify data to trigger other signals
        data = sample_15s_data.with_columns([
            pl.lit(40.0).alias("wae_explosion"),
            pl.lit(1.0).alias("wae_trend"),
            pl.lit(20.0).alias("wae_dead_zone"),
        ])
        
        # Set up for price break
        data = data.with_columns([
            pl.when(pl.arange(len(data)) == len(data) - 1)
            .then(5010.0)
            .otherwise(pl.col("close"))
            .alias("close")
        ])
        
        mock_suite.data.get_data.return_value = data
        
        generator = SignalGenerator(mock_suite)
        
        # Mock pattern check to return False
        with patch.object(generator, '_check_bullish_pattern', return_value=False):
            valid, signals = await generator.check_long_entry()
        
        assert valid is False  # Should fail without pattern
        assert signals["wae_explosion"] is True
        assert signals["price_break"] is True
        assert signals["pattern_edge"] is False
        assert signals["score"] == 0  # No score without pattern

    @pytest.mark.asyncio
    async def test_check_short_entry_with_all_signals(self, mock_suite, sample_15s_data):
        """Test short entry with all signals present including pattern."""
        # Modify data to trigger signals
        data = sample_15s_data.with_columns([
            pl.lit(40.0).alias("wae_explosion"),
            pl.lit(-1.0).alias("wae_trend"),  # Negative for short
            pl.lit(20.0).alias("wae_dead_zone"),
        ])
        
        # Set up for price break (current close < prev low)
        # Make the second-to-last low higher than the last close
        data = data.with_columns([
            pl.when(pl.arange(len(data)) == len(data) - 2)
            .then(5000.0)  # Set prev low higher
            .otherwise(pl.col("low"))
            .alias("low"),
            pl.when(pl.arange(len(data)) == len(data) - 1)
            .then(4990.0)  # Set current close lower
            .otherwise(pl.col("close"))
            .alias("close")
        ])
        
        mock_suite.data.get_data.return_value = data
        
        generator = SignalGenerator(mock_suite)
        
        # Mock pattern check to return True
        with patch.object(generator, '_check_bearish_pattern', return_value=True):
            valid, signals = await generator.check_short_entry()
        
        assert valid is True
        assert signals["wae_explosion"] is True
        assert signals["price_break"] is True
        assert signals["pattern_edge"] is True
        assert signals["signals_met"] == 3  # pattern + 2 other signals

    @pytest.mark.asyncio
    async def test_check_short_entry_without_pattern(self, mock_suite, sample_15s_data):
        """Test short entry fails without pattern even with other signals."""
        # Modify data to trigger other signals
        data = sample_15s_data.with_columns([
            pl.lit(40.0).alias("wae_explosion"),
            pl.lit(-1.0).alias("wae_trend"),
            pl.lit(20.0).alias("wae_dead_zone"),
        ])
        
        # Set up for price break
        data = data.with_columns([
            pl.when(pl.arange(len(data)) == len(data) - 1)
            .then(4990.0)
            .otherwise(pl.col("close"))
            .alias("close")
        ])
        
        mock_suite.data.get_data.return_value = data
        
        generator = SignalGenerator(mock_suite)
        
        # Mock pattern check to return False
        with patch.object(generator, '_check_bearish_pattern', return_value=False):
            valid, signals = await generator.check_short_entry()
        
        assert valid is False  # Should fail without pattern
        assert signals["wae_explosion"] is True
        assert signals["price_break"] is True
        assert signals["pattern_edge"] is False
        assert signals["score"] == 0  # No score without pattern

    @pytest.mark.asyncio
    async def test_check_bullish_pattern(self, mock_suite):
        """Test bullish pattern detection."""
        # Create 5min data with patterns
        data_5m = pl.DataFrame({
            "close": [5000.0] * 120,
            "high": [5005.0] * 120,
            "low": [4995.0] * 120,
            "volume": [100] * 120,
            "ob_bullish": [False] * 119 + [True],
            "ob_bottom": [None] * 119 + [4995.0],
            "fvg_bullish": [False] * 120,
        })
        
        data_15s = pl.DataFrame({
            "close": [5000.0],
        })
        
        mock_suite.data.get_data.side_effect = [data_5m, data_15s]
        
        generator = SignalGenerator(mock_suite)
        result = await generator._check_bullish_pattern()
        
        assert result is True

    @pytest.mark.asyncio
    async def test_check_bearish_pattern(self, mock_suite):
        """Test bearish pattern detection."""
        # Create 5min data with patterns
        data_5m = pl.DataFrame({
            "close": [5000.0] * 120,
            "high": [5005.0] * 120,
            "low": [4995.0] * 120,
            "volume": [100] * 120,
            "ob_bearish": [False] * 119 + [True],
            "ob_top": [None] * 119 + [5005.0],
            "fvg_bearish": [False] * 120,
        })
        
        data_15s = pl.DataFrame({
            "close": [5000.0],
        })
        
        mock_suite.data.get_data.side_effect = [data_5m, data_15s]
        
        generator = SignalGenerator(mock_suite)
        result = await generator._check_bearish_pattern()
        
        assert result is True

    @pytest.mark.asyncio
    async def test_get_microstructure_score(self, mock_suite, sample_15s_data):
        """Test microstructure score calculation."""
        # Add WAE data
        data = sample_15s_data.with_columns([
            pl.lit(30.0).alias("wae_explosion"),
        ])
        
        mock_suite.data.get_data.return_value = data
        
        generator = SignalGenerator(mock_suite)
        score = await generator.get_microstructure_score()
        
        assert isinstance(score, float)
        assert score >= 0.0

    @pytest.mark.asyncio
    async def test_detect_entry_signal_long(self, mock_suite):
        """Test detect_entry_signal for long signal."""
        generator = SignalGenerator(mock_suite)
        
        # Mock check methods
        with patch.object(generator, 'check_long_entry', return_value=(True, {"test": "long"})):
            with patch.object(generator, 'check_short_entry', return_value=(False, {})):
                signal_type, details = await generator.detect_entry_signal()
        
        assert signal_type == 1
        assert details == {"test": "long"}

    @pytest.mark.asyncio
    async def test_detect_entry_signal_short(self, mock_suite):
        """Test detect_entry_signal for short signal."""
        generator = SignalGenerator(mock_suite)
        
        # Mock check methods
        with patch.object(generator, 'check_long_entry', return_value=(False, {})):
            with patch.object(generator, 'check_short_entry', return_value=(True, {"test": "short"})):
                signal_type, details = await generator.detect_entry_signal()
        
        assert signal_type == -1
        assert details == {"test": "short"}

    @pytest.mark.asyncio
    async def test_detect_entry_signal_none(self, mock_suite):
        """Test detect_entry_signal with no signals."""
        generator = SignalGenerator(mock_suite)
        
        # Mock check methods
        with patch.object(generator, 'check_long_entry', return_value=(False, {})):
            with patch.object(generator, 'check_short_entry', return_value=(False, {})):
                signal_type, details = await generator.detect_entry_signal()
        
        assert signal_type == 0
        assert details == {}

    @pytest.mark.asyncio
    async def test_pattern_required_for_entry(self, mock_suite, sample_15s_data):
        """Test that pattern is mandatory for entry."""
        # Set up data with WAE and price signals but no pattern
        data = sample_15s_data.with_columns([
            pl.lit(40.0).alias("wae_explosion"),
            pl.lit(1.0).alias("wae_trend"),
            pl.lit(20.0).alias("wae_dead_zone"),
        ])
        
        mock_suite.data.get_data.return_value = data
        
        generator = SignalGenerator(mock_suite)
        
        # Pattern returns False
        with patch.object(generator, '_check_bullish_pattern', return_value=False):
            valid, signals = await generator.check_long_entry()
        
        # Should not enter without pattern
        assert valid is False
        assert signals["pattern_edge"] is False
        assert signals["score"] == 0

    @pytest.mark.asyncio
    async def test_minimum_signals_with_pattern(self, mock_suite, sample_15s_data):
        """Test that pattern plus one other signal is sufficient."""
        # Set up data with only WAE signal (no price break)
        data = sample_15s_data.with_columns([
            pl.lit(40.0).alias("wae_explosion"),
            pl.lit(1.0).alias("wae_trend"),
            pl.lit(20.0).alias("wae_dead_zone"),
        ])
        
        mock_suite.data.get_data.return_value = data
        
        generator = SignalGenerator(mock_suite)
        
        # Pattern returns True
        with patch.object(generator, '_check_bullish_pattern', return_value=True):
            valid, signals = await generator.check_long_entry()
        
        # Should enter with pattern + WAE even without price break
        assert valid is True
        assert signals["pattern_edge"] is True
        assert signals["wae_explosion"] is True
        assert signals["price_break"] is False
        assert signals["signals_met"] == 2  # pattern + wae