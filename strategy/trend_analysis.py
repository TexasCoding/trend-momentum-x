import logging
from typing import Literal

import polars as pl
from project_x_py import TradingSuite
from project_x_py.indicators import EMA, MACD, WAE

from utils import Config

TrendState = Literal["bullish", "bearish", "neutral"]
TradeMode = Literal["long_only", "short_only", "no_trade"]

class TrendAnalyzer:
    def __init__(self, suite: TradingSuite):
        self.suite = suite
        self.logger = logging.getLogger(__name__)
        self.ema_fast = Config.EMA_FAST
        self.ema_slow = Config.EMA_SLOW
        self.macd_fast = Config.MACD_FAST
        self.macd_slow = Config.MACD_SLOW
        self.macd_signal = Config.MACD_SIGNAL
        self.wae_sensitivity = Config.WAE_SENSITIVITY

    async def get_15min_trend(self) -> TrendState:
        data = await self.suite.data.get_data("15min", bars=200)
        if data.is_empty() or len(data) < self.ema_slow:
            self.logger.debug(f"15min: Not enough data (got {len(data)} bars, need {self.ema_slow})")
            return "neutral"

        data = (data
                .pipe(EMA, period=self.ema_fast)
                .pipe(EMA, period=self.ema_slow))

        last_row = data.tail(1)
        ema50 = last_row["ema_50"][0]
        ema200 = last_row["ema_200"][0]
        price = last_row["close"][0]

        self.logger.debug(f"15min: EMA50={ema50:.2f}, EMA200={ema200:.2f}, Price={price:.2f}")

        if ema50 > ema200 and price > ema50:
            self.logger.debug("15min trend is BULLISH (EMA50 > EMA200 and Price > EMA50)")
            return "bullish"
        elif ema50 < ema200 and price < ema50:
            self.logger.debug("15min trend is BEARISH (EMA50 < EMA200 and Price < EMA50)")
            return "bearish"
        else:
            self.logger.debug("15min trend is NEUTRAL (mixed signals)")
            return "neutral"

    async def get_5min_trend(self) -> TrendState:
        data = await self.suite.data.get_data("5min", bars=50)
        if data.is_empty() or len(data) < self.macd_slow + self.macd_signal:
            self.logger.debug(f"5min: Not enough data (got {len(data)} bars, need {self.macd_slow + self.macd_signal})")
            return "neutral"

        data = data.pipe(MACD, fast_period=self.macd_fast, slow_period=self.macd_slow, signal_period=self.macd_signal)

        hist_last3 = data.select(pl.col("macd_histogram").tail(3))["macd_histogram"]
        if len(hist_last3) < 3:
            self.logger.debug("5min: Not enough histogram data")
            return "neutral"

        hist_increasing = all(hist_last3[i] < hist_last3[i+1] for i in range(2))
        hist_decreasing = all(hist_last3[i] > hist_last3[i+1] for i in range(2))

        self.logger.debug(f"5min: MACD Hist last 3 bars: [{hist_last3[0]:.4f}, {hist_last3[1]:.4f}, {hist_last3[2]:.4f}]")
        self.logger.debug(f"5min: Histogram increasing={hist_increasing}, decreasing={hist_decreasing}")

        if hist_last3[2] > 0 and hist_increasing:
            self.logger.debug("5min trend is BULLISH (positive & increasing histogram)")
            return "bullish"
        elif hist_last3[2] < 0 and hist_decreasing:
            self.logger.debug("5min trend is BEARISH (negative & decreasing histogram)")
            return "bearish"
        else:
            self.logger.debug("5min trend is NEUTRAL (no clear momentum)")
            return "neutral"

    async def get_1min_trend(self) -> TrendState:
        data = await self.suite.data.get_data("1min", bars=120)
        if data.is_empty() or len(data) < 100:
            self.logger.debug(f"1min: Not enough data (got {len(data)} bars, need 100)")
            return "neutral"

        data = data.pipe(WAE, sensitivity=self.wae_sensitivity)

        last_row = data.tail(1)
        explosion = last_row["wae_explosion"][0]
        trend = last_row["wae_trend"][0]
        deadzone = last_row["wae_dead_zone"][0]

        self.logger.debug(f"1min: WAE Explosion={explosion:.4f}, Trend={trend:.4f}, DeadZone={deadzone:.4f}")
        self.logger.debug(f"1min: Explosion > DeadZone: {explosion > deadzone}")

        if explosion > deadzone:
            if trend > 0:
                self.logger.debug("1min trend is BULLISH (explosion above deadzone, positive trend)")
                return "bullish"
            elif trend < 0:
                self.logger.debug("1min trend is BEARISH (explosion above deadzone, negative trend)")
                return "bearish"

        self.logger.debug("1min trend is NEUTRAL (explosion below deadzone or no trend)")
        return "neutral"

    async def get_trade_mode(self) -> TradeMode:
        trend_15m = await self.get_15min_trend()
        trend_5m = await self.get_5min_trend()
        trend_1m = await self.get_1min_trend()

        trends = {
            "15min": trend_15m,
            "5min": trend_5m,
            "1min": trend_1m
        }

        # Count aligned trends - relax requirement from all 3 to at least 2
        bullish_count = sum(1 for t in trends.values() if t == "bullish")
        bearish_count = sum(1 for t in trends.values() if t == "bearish")

        self.logger.debug("="*60)
        self.logger.debug(f"TREND SUMMARY: 15m={trend_15m}, 5m={trend_5m}, 1m={trend_1m}")
        self.logger.debug(f"Bullish count: {bullish_count}, Bearish count: {bearish_count}")

        # Primary trend (15min) must be aligned, plus at least one other
        if trend_15m == "bullish" and bullish_count >= 2:
            self.logger.debug(f"TRADE MODE: LONG_ONLY (15min bullish + {bullish_count} bullish trends)")
            return "long_only"
        elif trend_15m == "bearish" and bearish_count >= 2:
            self.logger.debug(f"TRADE MODE: SHORT_ONLY (15min bearish + {bearish_count} bearish trends)")
            return "short_only"
        else:
            self.logger.debug("TRADE MODE: NO_TRADE (insufficient alignment)")
            return "no_trade"

    async def get_trend_details(self) -> dict:
        return {
            "15min": await self.get_15min_trend(),
            "5min": await self.get_5min_trend(),
            "1min": await self.get_1min_trend(),
            "trade_mode": await self.get_trade_mode()
        }
