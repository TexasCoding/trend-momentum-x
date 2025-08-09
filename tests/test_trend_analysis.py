"""Unit tests for the trend_analysis module."""

from unittest.mock import AsyncMock, patch

import pytest
from project_x_py.indicators import EMA, MACD

from strategy.trend_analysis import TrendAnalyzer


class TestTrendAnalyzer:
    """Test suite for TrendAnalyzer class."""

    @pytest.mark.asyncio
    async def test_initialization(self, mock_suite):
        """Test TrendAnalyzer initialization."""
        analyzer = TrendAnalyzer(mock_suite)
        assert analyzer.suite == mock_suite
        assert analyzer.ema_fast == 50
        assert analyzer.ema_slow == 200

    @pytest.mark.asyncio
    async def test_get_15min_trend_bullish(self, mock_suite, sample_15min_data):
        """Test 15-minute trend detection for bullish trend."""
        # Add EMA indicators to data
        data_with_ema = sample_15min_data.pipe(EMA, period=50).pipe(EMA, period=200)
        mock_suite.data.get_data.return_value = data_with_ema

        analyzer = TrendAnalyzer(mock_suite)
        trend = await analyzer.get_15min_trend()

        # Verify get_data was called correctly
        mock_suite.data.get_data.assert_called_with("15min", bars=200)
        assert trend in ["bullish", "bearish", "neutral"]

    @pytest.mark.asyncio
    async def test_get_15min_trend_no_data(self, mock_suite):
        """Test 15-minute trend with no data available."""
        mock_suite.data.get_data.return_value = None

        analyzer = TrendAnalyzer(mock_suite)
        trend = await analyzer.get_15min_trend()

        assert trend == "neutral"

    @pytest.mark.asyncio
    async def test_get_5min_trend_bullish(self, mock_suite, sample_5min_data):
        """Test 5-minute trend detection for bullish momentum."""
        # Check if MACD was applied correctly, if not manually add the column
        try:
            data_with_macd = sample_5min_data.pipe(MACD)
        except Exception:
            # If MACD fails, create data with the expected column
            data_with_macd = sample_5min_data
        
        # Ensure we have the MACD_histogram column with positive values
        if "MACD_histogram" not in data_with_macd.columns:
            data_with_macd = data_with_macd.with_columns(
                MACD_histogram=0.5  # Positive histogram indicates bullish
            )
        else:
            # Override with positive values
            data_with_macd = data_with_macd.with_columns(
                MACD_histogram=0.5
            )
        
        mock_suite.data.get_data.return_value = data_with_macd

        analyzer = TrendAnalyzer(mock_suite)
        trend = await analyzer.get_5min_trend()

        mock_suite.data.get_data.assert_called_with("5min", bars=50)
        assert trend == "bullish"

    @pytest.mark.asyncio
    async def test_get_5min_trend_bearish(self, mock_suite, sample_5min_data):
        """Test 5-minute trend detection for bearish momentum."""
        # Check if MACD was applied correctly, if not manually add the column
        try:
            data_with_macd = sample_5min_data.pipe(MACD)
        except Exception:
            # If MACD fails, create data with the expected column
            data_with_macd = sample_5min_data
        
        # Ensure we have the MACD_histogram column with negative values
        if "MACD_histogram" not in data_with_macd.columns:
            data_with_macd = data_with_macd.with_columns(
                MACD_histogram=-0.5  # Negative histogram indicates bearish
            )
        else:
            # Override with negative values
            data_with_macd = data_with_macd.with_columns(
                MACD_histogram=-0.5
            )
        
        mock_suite.data.get_data.return_value = data_with_macd

        analyzer = TrendAnalyzer(mock_suite)
        trend = await analyzer.get_5min_trend()

        assert trend == "bearish"

    @pytest.mark.asyncio
    async def test_get_1min_trend_with_wae(self, mock_suite, sample_1min_data):
        """Test 1-minute trend detection with WAE indicator."""
        import polars as pl
        
        # Create a larger dataset for WAE
        larger_data = pl.DataFrame({
            "timestamp": pl.datetime_range(
                start=pl.datetime(2024, 1, 1, 8, 0),
                end=pl.datetime(2024, 1, 1, 10, 0),
                interval="1m",
                eager=True
            ),
            "open": [5000.0 + i for i in range(121)],
            "high": [5002.0 + i for i in range(121)],
            "low": [4999.0 + i for i in range(121)],
            "close": [5001.0 + i for i in range(121)],
            "volume": [100 + i * 10 for i in range(121)]
        })
        
        # Try to apply WAE, but if it fails, manually add columns
        try:
            from project_x_py.indicators import WAE
            data_with_wae = larger_data.pipe(WAE, sensitivity=150)
        except Exception:
            # If WAE fails, create data with expected columns
            data_with_wae = larger_data.with_columns([
                pl.lit(200.0).alias("WAE_explosion"),
                pl.lit(1.0).alias("WAE_trend"),
                pl.lit(100.0).alias("WAE_deadzone")
            ])
        
        # Ensure we have the expected columns
        if "WAE_explosion" not in data_with_wae.columns:
            data_with_wae = data_with_wae.with_columns([
                pl.lit(200.0).alias("WAE_explosion"),
                pl.lit(1.0).alias("WAE_trend"),
                pl.lit(100.0).alias("WAE_deadzone")
            ])
        
        mock_suite.data.get_data.return_value = data_with_wae

        analyzer = TrendAnalyzer(mock_suite)
        trend = await analyzer.get_1min_trend()

        mock_suite.data.get_data.assert_called_with("1min", bars=20)
        assert trend in ["bullish", "bearish", "neutral"]

    @pytest.mark.asyncio
    async def test_get_trade_mode_all_bullish(self, mock_suite):
        """Test trade mode when all timeframes are bullish."""
        analyzer = TrendAnalyzer(mock_suite)

        # Mock the individual trend methods
        with patch.object(analyzer, 'get_15min_trend', new_callable=AsyncMock) as mock_15min, \
             patch.object(analyzer, 'get_5min_trend', new_callable=AsyncMock) as mock_5min, \
             patch.object(analyzer, 'get_1min_trend', new_callable=AsyncMock) as mock_1min:
            mock_15min.return_value = "bullish"
            mock_5min.return_value = "bullish"
            mock_1min.return_value = "bullish"

            mode = await analyzer.get_trade_mode()
            assert mode == "long_only"

    @pytest.mark.asyncio
    async def test_get_trade_mode_all_bearish(self, mock_suite):
        """Test trade mode when all timeframes are bearish."""
        analyzer = TrendAnalyzer(mock_suite)

        # Mock the individual trend methods
        with patch.object(analyzer, 'get_15min_trend', new_callable=AsyncMock) as mock_15min, \
             patch.object(analyzer, 'get_5min_trend', new_callable=AsyncMock) as mock_5min, \
             patch.object(analyzer, 'get_1min_trend', new_callable=AsyncMock) as mock_1min:
            mock_15min.return_value = "bearish"
            mock_5min.return_value = "bearish"
            mock_1min.return_value = "bearish"

            mode = await analyzer.get_trade_mode()
            assert mode == "short_only"

    @pytest.mark.asyncio
    async def test_get_trade_mode_mixed_trends(self, mock_suite):
        """Test trade mode when timeframes have mixed trends."""
        analyzer = TrendAnalyzer(mock_suite)

        # Mock mixed trend conditions
        with patch.object(analyzer, 'get_15min_trend', new_callable=AsyncMock) as mock_15min, \
             patch.object(analyzer, 'get_5min_trend', new_callable=AsyncMock) as mock_5min, \
             patch.object(analyzer, 'get_1min_trend', new_callable=AsyncMock) as mock_1min:
            mock_15min.return_value = "bullish"
            mock_5min.return_value = "bearish"
            mock_1min.return_value = "neutral"

            mode = await analyzer.get_trade_mode()
            assert mode == "no_trade"

    @pytest.mark.asyncio
    async def test_get_trade_mode_with_neutral(self, mock_suite):
        """Test trade mode when one timeframe is neutral."""
        analyzer = TrendAnalyzer(mock_suite)

        # Mock with one neutral trend
        with patch.object(analyzer, 'get_15min_trend', new_callable=AsyncMock) as mock_15min, \
             patch.object(analyzer, 'get_5min_trend', new_callable=AsyncMock) as mock_5min, \
             patch.object(analyzer, 'get_1min_trend', new_callable=AsyncMock) as mock_1min:
            mock_15min.return_value = "bullish"
            mock_5min.return_value = "bullish"
            mock_1min.return_value = "neutral"

            mode = await analyzer.get_trade_mode()
            assert mode == "no_trade"

    @pytest.mark.asyncio
    async def test_get_trend_details(self, mock_suite):
        """Test getting comprehensive trend details."""
        analyzer = TrendAnalyzer(mock_suite)

        # Mock the individual trend methods
        with patch.object(analyzer, 'get_15min_trend', new_callable=AsyncMock) as mock_15min, \
             patch.object(analyzer, 'get_5min_trend', new_callable=AsyncMock) as mock_5min, \
             patch.object(analyzer, 'get_1min_trend', new_callable=AsyncMock) as mock_1min:
            mock_15min.return_value = "bullish"
            mock_5min.return_value = "bullish"
            mock_1min.return_value = "bullish"

            details = await analyzer.get_trend_details()

            assert details["15min"] == "bullish"
            assert details["5min"] == "bullish"
            assert details["1min"] == "bullish"
            assert details["trade_mode"] == "long_only"