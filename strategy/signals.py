
import logging

import polars as pl
from project_x_py import TradingSuite
from project_x_py.indicators import FVG, ORDERBLOCK, RSI, WAE

from utils import Config


class SignalGenerator:
    def __init__(self, suite: TradingSuite):
        self.suite = suite
        self.logger = logging.getLogger(__name__)
        self.rsi_period = Config.RSI_PERIOD
        self.rsi_oversold = Config.RSI_OVERSOLD
        self.rsi_overbought = Config.RSI_OVERBOUGHT
        self.rsi_long_cross = Config.RSI_LONG_CROSS
        self.rsi_short_cross = Config.RSI_SHORT_CROSS
        self.rsi_lookback = Config.RSI_LOOKBACK_BARS
        self.wae_sensitivity = Config.WAE_SENSITIVITY

        # Signal requirement configuration
        self.min_signals_required = Config.MIN_SIGNALS_REQUIRED
        self.pattern_required = Config.PATTERN_REQUIRED

        # Signal weights for scoring
        self.weight_rsi = Config.WEIGHT_RSI
        self.weight_wae = Config.WEIGHT_WAE
        self.weight_price = Config.WEIGHT_PRICE
        self.weight_pattern = Config.WEIGHT_PATTERN

        # Pattern detection thresholds
        # NOTE: These are not in Config, using hardcoded values
        self.ob_volume_percentile = 70
        self.fvg_min_gap_size = 0.001

    async def check_long_entry(self) -> tuple[bool, dict]:
        self.logger.debug("="*60)
        self.logger.debug("CHECKING LONG ENTRY SIGNALS")

        signals = {
            "rsi_cross": False,
            "wae_explosion": False,
            "price_break": False,
            "pattern_edge": False,
            "details": {}
        }

        # Fetch more bars for WAE (needs 100+) and RSI lookback
        data_15s = await self.suite.data.get_data("15sec", bars=120)
        if data_15s is None or len(data_15s) < 100:
            self.logger.debug(f"Insufficient data for long entry check (got {len(data_15s) if data_15s is not None else 0} bars)")
            return False, signals

        data_15s = (data_15s
                   .pipe(RSI, period=self.rsi_period)
                   .pipe(WAE, sensitivity=self.wae_sensitivity))

        # Check for recent dip below oversold
        rsi_series = data_15s["rsi_14"]
        last_rsi = rsi_series.tail(1)[0]
        prev_rsi = rsi_series.tail(2)[0]

        recent_rsi = rsi_series.tail(self.rsi_lookback)[:-1]
        recently_oversold = len([x for x in recent_rsi if x < self.rsi_oversold]) > 0
        rsi_crossed_up = prev_rsi < self.rsi_long_cross and last_rsi >= self.rsi_long_cross

        signals["rsi_cross"] = recently_oversold and rsi_crossed_up
        self.logger.debug(f"RSI: prev={prev_rsi:.2f}, current={last_rsi:.2f}, oversold={recently_oversold}, crossed_up={rsi_crossed_up}")
        self.logger.debug(f"  ✓ RSI Cross Signal: {signals['rsi_cross']}")

        last_two_rows = data_15s.tail(2)
        prev_high = last_two_rows["high"][0]
        current_close = last_two_rows["close"][1]

        last_wae = data_15s.tail(1)
        explosion = last_wae["wae_explosion"][0]
        trend = last_wae["wae_trend"][0]
        deadzone = last_wae["wae_dead_zone"][0]
        signals["wae_explosion"] = explosion > deadzone and trend > 0
        self.logger.debug(f"WAE: explosion={explosion:.4f}, trend={trend:.4f}, deadzone={deadzone:.4f}")
        self.logger.debug(f"  ✓ WAE Explosion Signal: {signals['wae_explosion']}")

        signals["price_break"] = current_close > prev_high
        self.logger.debug(f"Price: close={current_close:.2f}, prev_high={prev_high:.2f}")
        self.logger.debug(f"  ✓ Price Break Signal: {signals['price_break']}")

        signals["pattern_edge"] = await self._check_bullish_pattern()
        self.logger.debug(f"  ✓ Pattern Edge Signal: {signals['pattern_edge']}")

        signals["details"] = {
            "rsi": {"prev": prev_rsi, "current": last_rsi, "recently_oversold": recently_oversold},
            "wae": {"explosion": explosion, "trend": trend, "deadzone": deadzone},
            "price": {"close": current_close, "prev_high": prev_high}
        }

        # Calculate weighted score instead of requiring all signals
        signal_score = 0.0
        total_weight = 0.0

        if signals["rsi_cross"]:
            signal_score += self.weight_rsi
        total_weight += self.weight_rsi

        if signals["wae_explosion"]:
            signal_score += self.weight_wae
        total_weight += self.weight_wae

        if signals["price_break"]:
            signal_score += self.weight_price
        total_weight += self.weight_price

        # Pattern is optional unless specifically required
        if self.pattern_required:
            if signals["pattern_edge"]:
                signal_score += self.weight_pattern
            total_weight += self.weight_pattern
        elif signals["pattern_edge"]:
            # Bonus if pattern exists but not required
            signal_score += self.weight_pattern * 0.5

        # Calculate how many core signals are met (excluding pattern if not required)
        core_signals = ["rsi_cross", "wae_explosion", "price_break"]
        if self.pattern_required:
            core_signals.append("pattern_edge")

        signals_met = sum(1 for s in core_signals if signals[s])

        # Check if we meet minimum requirements
        all_signals = signals_met >= self.min_signals_required

        # Add score to signals for debugging
        signals["score"] = signal_score
        signals["max_score"] = total_weight
        signals["signals_met"] = signals_met

        self.logger.debug(f"LONG ENTRY: {signals_met}/{len(core_signals)} signals met (need {self.min_signals_required})")
        self.logger.debug(f"  Score: {signal_score:.2f}/{total_weight:.2f} ({signal_score/total_weight*100:.1f}%)")
        self.logger.debug(f"LONG ENTRY RESULT: {'✅ SUFFICIENT SIGNALS' if all_signals else '❌ INSUFFICIENT SIGNALS'}")
        if not all_signals:
            missing = [k for k in core_signals if not signals[k]]
            self.logger.debug(f"  Missing signals: {', '.join(missing)}")

        return all_signals, signals

    async def check_short_entry(self) -> tuple[bool, dict]:
        self.logger.debug("="*60)
        self.logger.debug("CHECKING SHORT ENTRY SIGNALS")

        signals = {
            "rsi_cross": False,
            "wae_explosion": False,
            "price_break": False,
            "pattern_edge": False,
            "details": {}
        }

        data_15s = await self.suite.data.get_data("15sec", bars=120)
        if data_15s is None or len(data_15s) < 100:
            self.logger.debug(f"Insufficient data for short entry check (got {len(data_15s) if data_15s is not None else 0} bars)")
            return False, signals

        data_15s = (data_15s
                   .pipe(RSI, period=self.rsi_period)
                   .pipe(WAE, sensitivity=self.wae_sensitivity))

        rsi_series = data_15s["rsi_14"]
        last_rsi = rsi_series.tail(1)[0]
        prev_rsi = rsi_series.tail(2)[0]

        # Look back further for overbought condition
        recent_rsi = rsi_series.tail(self.rsi_lookback)[:-1]
        recently_overbought = len([x for x in recent_rsi if x > self.rsi_overbought]) > 0
        rsi_crossed_down = prev_rsi > self.rsi_short_cross and last_rsi <= self.rsi_short_cross

        signals["rsi_cross"] = recently_overbought and rsi_crossed_down
        self.logger.debug(f"RSI: prev={prev_rsi:.2f}, current={last_rsi:.2f}, overbought={recently_overbought}, crossed_down={rsi_crossed_down}")
        self.logger.debug(f"  ✓ RSI Cross Signal: {signals['rsi_cross']}")

        last_two_rows = data_15s.tail(2)
        prev_low = last_two_rows["low"][0]
        current_close = last_two_rows["close"][1]

        last_wae = data_15s.tail(1)
        explosion = last_wae["wae_explosion"][0]
        trend = last_wae["wae_trend"][0]
        deadzone = last_wae["wae_dead_zone"][0]
        signals["wae_explosion"] = explosion > deadzone and trend < 0
        self.logger.debug(f"WAE: explosion={explosion:.4f}, trend={trend:.4f}, deadzone={deadzone:.4f}")
        self.logger.debug(f"  ✓ WAE Explosion Signal: {signals['wae_explosion']}")

        signals["price_break"] = current_close < prev_low
        self.logger.debug(f"Price: close={current_close:.2f}, prev_low={prev_low:.2f}")
        self.logger.debug(f"  ✓ Price Break Signal: {signals['price_break']}")

        signals["pattern_edge"] = await self._check_bearish_pattern()
        self.logger.debug(f"  ✓ Pattern Edge Signal: {signals['pattern_edge']}")

        signals["details"] = {
            "rsi": {"prev": prev_rsi, "current": last_rsi, "recently_overbought": recently_overbought},
            "wae": {"explosion": explosion, "trend": trend, "deadzone": deadzone},
            "price": {"close": current_close, "prev_low": prev_low}
        }

        # Calculate weighted score instead of requiring all signals
        signal_score = 0.0
        total_weight = 0.0

        if signals["rsi_cross"]:
            signal_score += self.weight_rsi
        total_weight += self.weight_rsi

        if signals["wae_explosion"]:
            signal_score += self.weight_wae
        total_weight += self.weight_wae

        if signals["price_break"]:
            signal_score += self.weight_price
        total_weight += self.weight_price

        # Pattern is optional unless specifically required
        if self.pattern_required:
            if signals["pattern_edge"]:
                signal_score += self.weight_pattern
            total_weight += self.weight_pattern
        elif signals["pattern_edge"]:
            # Bonus if pattern exists but not required
            signal_score += self.weight_pattern * 0.5

        # Calculate how many core signals are met (excluding pattern if not required)
        core_signals = ["rsi_cross", "wae_explosion", "price_break"]
        if self.pattern_required:
            core_signals.append("pattern_edge")

        signals_met = sum(1 for s in core_signals if signals[s])

        # Check if we meet minimum requirements
        all_signals = signals_met >= self.min_signals_required

        # Add score to signals for debugging
        signals["score"] = signal_score
        signals["max_score"] = total_weight
        signals["signals_met"] = signals_met

        self.logger.debug(f"SHORT ENTRY: {signals_met}/{len(core_signals)} signals met (need {self.min_signals_required})")
        self.logger.debug(f"  Score: {signal_score:.2f}/{total_weight:.2f} ({signal_score/total_weight*100:.1f}%)")
        self.logger.debug(f"SHORT ENTRY RESULT: {'✅ SUFFICIENT SIGNALS' if all_signals else '❌ INSUFFICIENT SIGNALS'}")
        if not all_signals:
            missing = [k for k in core_signals if not signals[k]]
            self.logger.debug(f"  Missing signals: {', '.join(missing)}")

        return all_signals, signals

    async def _check_bullish_pattern(self) -> bool:
        data_5m = await self.suite.data.get_data("5min", bars=120)
        if data_5m is None or len(data_5m) < 120:
            self.logger.debug("  Pattern check: Insufficient 5min data")
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
        if "ob_bullish" in last_row.columns and last_row["ob_bullish"][0] and "ob_bottom" in last_row.columns:
            ob_bottom = last_row["ob_bottom"][0]
            if ob_bottom is not None:
                has_bullish_ob = current_price >= ob_bottom
                self.logger.debug(f"  Bullish OB: Found at {ob_bottom:.2f}, price={current_price:.2f}, valid={has_bullish_ob}")

        has_fvg_fill = False
        if "fvg_bullish" in last_row.columns and last_row["fvg_bullish"][0]:
            has_fvg_fill = True
            if "fvg_gap_bottom" in last_row.columns:
                gap_bottom = last_row["fvg_gap_bottom"][0]
                if gap_bottom is not None:
                    self.logger.debug(f"  Bullish FVG: Found with bottom at {gap_bottom:.2f}")
                else:
                    self.logger.debug("  Bullish FVG: Found")

        result = has_bullish_ob or has_fvg_fill
        self.logger.debug(f"  Pattern result: OB={has_bullish_ob}, FVG={has_fvg_fill}, Final={result}")
        return result

    async def _check_bearish_pattern(self) -> bool:
        data_5m = await self.suite.data.get_data("5min", bars=120)
        if data_5m is None or len(data_5m) < 120:
            self.logger.debug("  Pattern check: Insufficient 5min data")
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
        if "ob_bearish" in last_row.columns and last_row["ob_bearish"][0] and "ob_top" in last_row.columns:
            ob_top = last_row["ob_top"][0]
            if ob_top is not None:
                has_bearish_ob = current_price <= ob_top
                self.logger.debug(f"  Bearish OB: Found at {ob_top:.2f}, price={current_price:.2f}, valid={has_bearish_ob}")

        has_fvg_fill = False
        if "fvg_bearish" in last_row.columns and last_row["fvg_bearish"][0]:
            has_fvg_fill = True
            if "fvg_gap_top" in last_row.columns:
                gap_top = last_row["fvg_gap_top"][0]
                if gap_top is not None:
                    self.logger.debug(f"  Bearish FVG: Found with top at {gap_top:.2f}")
                else:
                    self.logger.debug("  Bearish FVG: Found")

        result = has_bearish_ob or has_fvg_fill
        self.logger.debug(f"  Pattern result: OB={has_bearish_ob}, FVG={has_fvg_fill}, Final={result}")
        return result

    async def get_microstructure_score(self) -> float:
        data_15s = await self.suite.data.get_data("15sec", bars=120)
        if data_15s is None or len(data_15s) < 100:
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

        wae_strength = data_15s.tail(1)["wae_explosion"][0] / self.wae_sensitivity

        return float(divergence_score * wae_strength)
