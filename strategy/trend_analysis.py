from typing import Literal

import polars as pl
from project_x_py import TradingSuite
from project_x_py.indicators import EMA, MACD, WAE

TrendState = Literal["bullish", "bearish", "neutral"]
TradeMode = Literal["long_only", "short_only", "no_trade"]

class TrendAnalyzer:
    def __init__(self, suite: TradingSuite):
        self.suite = suite
        self.ema_fast = 50
        self.ema_slow = 200
        self.macd_fast = 12
        self.macd_slow = 26
        self.macd_signal = 9
        self.wae_sensitivity = 150

    async def get_15min_trend(self) -> TrendState:
        data = await self.suite.data.get_data("15min", bars=200)
        if data is None or len(data) < self.ema_slow:
            return "neutral"

        data = (data
                .pipe(EMA, period=self.ema_fast)
                .pipe(EMA, period=self.ema_slow))
        data = data.rename({f"EMA_{self.ema_fast}": "EMA_50", f"EMA_{self.ema_slow}": "EMA_200"})

        last_row = data.tail(1)
        ema50 = last_row["EMA_50"][0]
        ema200 = last_row["EMA_200"][0]
        price = last_row["close"][0]

        if ema50 > ema200 and price > ema50:
            return "bullish"
        elif ema50 < ema200 and price < ema50:
            return "bearish"
        else:
            return "neutral"

    async def get_5min_trend(self) -> TrendState:
        data = await self.suite.data.get_data("5min", bars=50)
        if data is None or len(data) < self.macd_slow + self.macd_signal:
            return "neutral"

        data = data.pipe(MACD, fast_period=self.macd_fast, slow_period=self.macd_slow, signal_period=self.macd_signal)

        hist_last3 = data.select(pl.col("MACD_hist").tail(3))["MACD_hist"]
        if len(hist_last3) < 3:
            return "neutral"

        hist_increasing = all(hist_last3[i] < hist_last3[i+1] for i in range(2))
        hist_decreasing = all(hist_last3[i] > hist_last3[i+1] for i in range(2))

        if hist_last3[2] > 0 and hist_increasing:
            return "bullish"
        elif hist_last3[2] < 0 and hist_decreasing:
            return "bearish"
        else:
            return "neutral"

    async def get_1min_trend(self) -> TrendState:
        data = await self.suite.data.get_data("1min", bars=20)
        if data is None or len(data) < 20:
            return "neutral"

        data = data.pipe(WAE, sensitivity=self.wae_sensitivity)

        last_row = data.tail(1)
        explosion = last_row["WAE_explosion"][0]
        trend = last_row["WAE_trend"][0]
        deadzone = last_row["WAE_deadzone"][0]

        if explosion > deadzone:
            if trend > 0:
                return "bullish"
            elif trend < 0:
                return "bearish"

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

        if all(t == "bullish" for t in trends.values()):
            return "long_only"
        elif all(t == "bearish" for t in trends.values()):
            return "short_only"
        else:
            return "no_trade"

    async def get_trend_details(self) -> dict:
        return {
            "15min": await self.get_15min_trend(),
            "5min": await self.get_5min_trend(),
            "1min": await self.get_1min_trend(),
            "trade_mode": await self.get_trade_mode()
        }
