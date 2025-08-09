
import polars as pl
from project_x_py import TradingSuite
from project_x_py.indicators import FVG, ORDERBLOCK, RSI, WAE

from utils import Config


class SignalGenerator:
    def __init__(self, suite: TradingSuite):
        self.suite = suite
        self.rsi_period = Config.RSI_PERIOD
        self.rsi_oversold = Config.RSI_OVERSOLD
        self.rsi_overbought = Config.RSI_OVERBOUGHT
        self.rsi_long_cross = Config.RSI_LONG_CROSS
        self.rsi_short_cross = Config.RSI_SHORT_CROSS
        self.wae_sensitivity = Config.WAE_SENSITIVITY
        # NOTE: These are not in Config, using hardcoded values
        self.ob_volume_percentile = 70
        self.fvg_min_gap_size = 0.001

    async def check_long_entry(self) -> tuple[bool, dict]:
        signals = {
            "rsi_cross": False,
            "wae_explosion": False,
            "price_break": False,
            "pattern_edge": False,
            "details": {}
        }

        # Fetch more bars for RSI lookback
        data_15s = await self.suite.data.get_data("15sec", bars=self.rsi_period + 10)
        if data_15s is None or len(data_15s) < self.rsi_period + 2:
            return False, signals

        data_15s = (data_15s
                   .pipe(RSI, period=self.rsi_period)
                   .pipe(WAE, sensitivity=self.wae_sensitivity))

        # Check for recent dip below oversold
        rsi_series = data_15s["RSI_14"]
        last_rsi = rsi_series.tail(1)[0]
        prev_rsi = rsi_series.tail(2)[0]

        recent_rsi = rsi_series.tail(10)[:-1]
        recently_oversold = len([x for x in recent_rsi if x < self.rsi_oversold]) > 0
        rsi_crossed_up = prev_rsi < self.rsi_long_cross and last_rsi >= self.rsi_long_cross

        signals["rsi_cross"] = recently_oversold and rsi_crossed_up

        last_two_rows = data_15s.tail(2)
        prev_high = last_two_rows["high"][0]
        current_close = last_two_rows["close"][1]

        last_wae = data_15s.tail(1)
        explosion = last_wae["WAE_explosion"][0]
        trend = last_wae["WAE_trend"][0]
        deadzone = last_wae["WAE_deadzone"][0]
        signals["wae_explosion"] = explosion > deadzone and trend > 0

        signals["price_break"] = current_close > prev_high

        signals["pattern_edge"] = await self._check_bullish_pattern()

        signals["details"] = {
            "rsi": {"prev": prev_rsi, "current": last_rsi, "recently_oversold": recently_oversold},
            "wae": {"explosion": explosion, "trend": trend, "deadzone": deadzone},
            "price": {"close": current_close, "prev_high": prev_high}
        }

        all_signals = all([
            signals["rsi_cross"],
            signals["wae_explosion"],
            signals["price_break"],
            signals["pattern_edge"]
        ])

        return all_signals, signals

    async def check_short_entry(self) -> tuple[bool, dict]:
        signals = {
            "rsi_cross": False,
            "wae_explosion": False,
            "price_break": False,
            "pattern_edge": False,
            "details": {}
        }

        data_15s = await self.suite.data.get_data("15sec", bars=self.rsi_period + 10)
        if data_15s is None or len(data_15s) < self.rsi_period + 2:
            return False, signals

        data_15s = (data_15s
                   .pipe(RSI, period=self.rsi_period)
                   .pipe(WAE, sensitivity=self.wae_sensitivity))

        rsi_series = data_15s["RSI_14"]
        last_rsi = rsi_series.tail(1)[0]
        prev_rsi = rsi_series.tail(2)[0]

        recent_rsi = rsi_series.tail(10)[:-1]
        recently_overbought = len([x for x in recent_rsi if x > self.rsi_overbought]) > 0
        rsi_crossed_down = prev_rsi > self.rsi_short_cross and last_rsi <= self.rsi_short_cross

        signals["rsi_cross"] = recently_overbought and rsi_crossed_down

        last_two_rows = data_15s.tail(2)
        prev_low = last_two_rows["low"][0]
        current_close = last_two_rows["close"][1]

        last_wae = data_15s.tail(1)
        explosion = last_wae["WAE_explosion"][0]
        trend = last_wae["WAE_trend"][0]
        deadzone = last_wae["WAE_deadzone"][0]
        signals["wae_explosion"] = explosion > deadzone and trend < 0

        signals["price_break"] = current_close < prev_low

        signals["pattern_edge"] = await self._check_bearish_pattern()

        signals["details"] = {
            "rsi": {"prev": prev_rsi, "current": last_rsi, "recently_overbought": recently_overbought},
            "wae": {"explosion": explosion, "trend": trend, "deadzone": deadzone},
            "price": {"close": current_close, "prev_low": prev_low}
        }

        all_signals = all([
            signals["rsi_cross"],
            signals["wae_explosion"],
            signals["price_break"],
            signals["pattern_edge"]
        ])

        return all_signals, signals

    async def _check_bullish_pattern(self) -> bool:
        data_5m = await self.suite.data.get_data("5min", bars=20)
        if data_5m is None or len(data_5m) < 20:
            return False

        data_5m = (data_5m
                  .pipe(FVG, min_gap_size=self.fvg_min_gap_size, check_mitigation=True)
                  .pipe(ORDERBLOCK, min_volume_percentile=self.ob_volume_percentile))

        last_row = data_5m.tail(1)
        data_15s = await self.suite.data.get_data("15sec")
        if data_15s is None:
            return False
        current_price = data_15s.tail(1)["close"][0]

        has_bullish_ob = False
        if "ORDERBLOCK_type" in last_row.columns and last_row["ORDERBLOCK_type"][0] == "bullish" and "ORDERBLOCK_low" in last_row.columns:
            ob_low = last_row["ORDERBLOCK_low"][0]
            has_bullish_ob = current_price >= ob_low

        has_fvg_fill = False
        if "FVG_type" in last_row.columns and last_row["FVG_type"][0] == "bullish":
            has_fvg_fill = True

        return has_bullish_ob or has_fvg_fill

    async def _check_bearish_pattern(self) -> bool:
        data_5m = await self.suite.data.get_data("5min", bars=20)
        if data_5m is None or len(data_5m) < 20:
            return False

        data_5m = (data_5m
                  .pipe(FVG, min_gap_size=self.fvg_min_gap_size, check_mitigation=True)
                  .pipe(ORDERBLOCK, min_volume_percentile=self.ob_volume_percentile))

        last_row = data_5m.tail(1)
        data_15s = await self.suite.data.get_data("15sec")
        if data_15s is None:
            return False
        current_price = data_15s.tail(1)["close"][0]

        has_bearish_ob = False
        if "ORDERBLOCK_type" in last_row.columns and last_row["ORDERBLOCK_type"][0] == "bearish" and "ORDERBLOCK_high" in last_row.columns:
            ob_high = last_row["ORDERBLOCK_high"][0]
            has_bearish_ob = current_price <= ob_high

        has_fvg_fill = False
        if "FVG_type" in last_row.columns and last_row["FVG_type"][0] == "bearish":
            has_fvg_fill = True

        return has_bearish_ob or has_fvg_fill

    async def get_microstructure_score(self) -> float:
        data_15s = await self.suite.data.get_data("15sec", bars=20)
        if data_15s is None or len(data_15s) < 20:
            return 0.0

        data_15s = (data_15s
                   .pipe(RSI, period=self.rsi_period)
                   .pipe(WAE, sensitivity=self.wae_sensitivity))

        rsi_values = data_15s.select(pl.col("RSI_14").tail(5))["RSI_14"]
        price_values = data_15s.select(pl.col("close").tail(5))["close"]

        if len(rsi_values) < 5 or len(price_values) < 5:
            return 0.0

        price_trend = (price_values[-1] - price_values[0]) / price_values[0]
        rsi_trend = (rsi_values[-1] - rsi_values[0]) / 100

        divergence_score = abs(rsi_trend - price_trend)

        wae_strength = data_15s.tail(1)["WAE_explosion"][0] / self.wae_sensitivity

        return float(divergence_score * wae_strength)
