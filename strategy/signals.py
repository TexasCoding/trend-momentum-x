import logging

import polars as pl
from project_x_py import TradingSuite
from project_x_py.indicators import FVG, ORDERBLOCK, WAE

from utils import Config


class SignalGenerator:
    def __init__(self, suite: TradingSuite):
        self.suite = suite
        self.logger = logging.getLogger(__name__)
        self.wae_sensitivity = Config.WAE_SENSITIVITY

        # Signal requirement configuration - patterns are now required
        self.min_signals_required = 2  # Need at least 2 out of 3 core signals
        self.pattern_required = True  # Patterns (OB/FVG) are now mandatory

        # Signal weights for scoring - adjusted for pattern emphasis
        self.weight_wae = Config.WEIGHT_WAE  # WAE weight (1.5)
        self.weight_price = Config.WEIGHT_PRICE  # Price break weight (1.0)
        self.weight_pattern = 2.0  # Increase pattern weight significantly

        # Pattern detection thresholds
        self.ob_volume_percentile = 70
        self.fvg_min_gap_size = 0.001

    async def check_long_entry(self) -> tuple[bool, dict]:
        self.logger.debug("=" * 60)
        self.logger.debug("CHECKING LONG ENTRY SIGNALS")

        signals = {
            "wae_explosion": False,
            "price_break": False,
            "pattern_edge": False,
            "details": {},
        }

        # Fetch bars for WAE (needs 100+)
        data_15s = await self.suite.data.get_data("15sec", bars=120)
        if data_15s is None or len(data_15s) < 100:
            self.logger.debug(
                f"Insufficient data for long entry check (got {len(data_15s) if data_15s is not None else 0} bars)"
            )
            return False, signals

        data_15s = data_15s.pipe(WAE, sensitivity=self.wae_sensitivity)

        # Check WAE explosion
        last_wae = data_15s.tail(1)
        explosion = last_wae["wae_explosion"][0]
        trend = last_wae["wae_trend"][0]
        deadzone = last_wae["wae_dead_zone"][0]
        signals["wae_explosion"] = explosion > deadzone and trend > 0
        self.logger.debug(
            f"WAE: explosion={explosion:.4f}, trend={trend:.4f}, deadzone={deadzone:.4f}"
        )
        self.logger.debug(f"  ✓ WAE Explosion Signal: {signals['wae_explosion']}")

        # Check price breakout
        last_two_rows = data_15s.tail(2)
        prev_high = last_two_rows["high"][0]
        current_close = last_two_rows["close"][1]
        signals["price_break"] = current_close > prev_high
        self.logger.debug(f"Price: close={current_close:.2f}, prev_high={prev_high:.2f}")
        self.logger.debug(f"  ✓ Price Break Signal: {signals['price_break']}")

        # Check patterns (OB/FVG) - now critical
        signals["pattern_edge"] = await self._check_bullish_pattern()
        self.logger.debug(f"  ✓ Pattern Edge Signal (REQUIRED): {signals['pattern_edge']}")

        signals["details"] = {
            "wae": {"explosion": explosion, "trend": trend, "deadzone": deadzone},
            "price": {"close": current_close, "prev_high": prev_high},
        }

        # Calculate weighted score with pattern as mandatory
        signal_score = 0.0
        total_weight = 0.0

        # Pattern MUST be present (mandatory signal)
        if not signals["pattern_edge"]:
            self.logger.debug("❌ PATTERN REQUIRED BUT NOT FOUND - NO ENTRY")
            signals["score"] = 0
            signals["max_score"] = 0
            signals["signals_met"] = 0
            return False, signals

        signal_score += self.weight_pattern
        total_weight += self.weight_pattern

        if signals["wae_explosion"]:
            signal_score += self.weight_wae
        total_weight += self.weight_wae

        if signals["price_break"]:
            signal_score += self.weight_price
        total_weight += self.weight_price

        # Core signals now exclude RSI, include pattern as mandatory
        core_signals = ["wae_explosion", "price_break"]
        signals_met = sum(1 for s in core_signals if signals[s])

        # Need at least 1 of the 2 core signals (pattern is already confirmed)
        all_signals = signals_met >= 1

        # Add score to signals for debugging
        signals["score"] = signal_score
        signals["max_score"] = total_weight
        signals["signals_met"] = signals_met + 1  # +1 for the mandatory pattern

        self.logger.debug(
            f"LONG ENTRY: Pattern ✓ + {signals_met}/{len(core_signals)} other signals"
        )
        self.logger.debug(
            f"  Score: {signal_score:.2f}/{total_weight:.2f} ({signal_score / total_weight * 100:.1f}%)"
        )
        self.logger.debug(
            f"LONG ENTRY RESULT: {'✅ SUFFICIENT SIGNALS' if all_signals else '❌ INSUFFICIENT SIGNALS'}"
        )
        if not all_signals:
            missing = [k for k in core_signals if not signals[k]]
            self.logger.debug(f"  Missing signals: {', '.join(missing)}")

        return all_signals, signals

    async def check_short_entry(self) -> tuple[bool, dict]:
        self.logger.debug("=" * 60)
        self.logger.debug("CHECKING SHORT ENTRY SIGNALS")

        signals = {
            "wae_explosion": False,
            "price_break": False,
            "pattern_edge": False,
            "details": {},
        }

        data_15s = await self.suite.data.get_data("15sec", bars=120)
        if data_15s is None or len(data_15s) < 100:
            self.logger.debug(
                f"Insufficient data for short entry check (got {len(data_15s) if data_15s is not None else 0} bars)"
            )
            return False, signals

        data_15s = data_15s.pipe(WAE, sensitivity=self.wae_sensitivity)

        # Check WAE explosion
        last_wae = data_15s.tail(1)
        explosion = last_wae["wae_explosion"][0]
        trend = last_wae["wae_trend"][0]
        deadzone = last_wae["wae_dead_zone"][0]
        signals["wae_explosion"] = explosion > deadzone and trend < 0
        self.logger.debug(
            f"WAE: explosion={explosion:.4f}, trend={trend:.4f}, deadzone={deadzone:.4f}"
        )
        self.logger.debug(f"  ✓ WAE Explosion Signal: {signals['wae_explosion']}")

        # Check price breakout
        last_two_rows = data_15s.tail(2)
        prev_low = last_two_rows["low"][0]
        current_close = last_two_rows["close"][1]
        signals["price_break"] = current_close < prev_low
        self.logger.debug(f"Price: close={current_close:.2f}, prev_low={prev_low:.2f}")
        self.logger.debug(f"  ✓ Price Break Signal: {signals['price_break']}")

        # Check patterns (OB/FVG) - now critical
        signals["pattern_edge"] = await self._check_bearish_pattern()
        self.logger.debug(f"  ✓ Pattern Edge Signal (REQUIRED): {signals['pattern_edge']}")

        signals["details"] = {
            "wae": {"explosion": explosion, "trend": trend, "deadzone": deadzone},
            "price": {"close": current_close, "prev_low": prev_low},
        }

        # Calculate weighted score with pattern as mandatory
        signal_score = 0.0
        total_weight = 0.0

        # Pattern MUST be present (mandatory signal)
        if not signals["pattern_edge"]:
            self.logger.debug("❌ PATTERN REQUIRED BUT NOT FOUND - NO ENTRY")
            signals["score"] = 0
            signals["max_score"] = 0
            signals["signals_met"] = 0
            return False, signals

        signal_score += self.weight_pattern
        total_weight += self.weight_pattern

        if signals["wae_explosion"]:
            signal_score += self.weight_wae
        total_weight += self.weight_wae

        if signals["price_break"]:
            signal_score += self.weight_price
        total_weight += self.weight_price

        # Core signals now exclude RSI, include pattern as mandatory
        core_signals = ["wae_explosion", "price_break"]
        signals_met = sum(1 for s in core_signals if signals[s])

        # Need at least 1 of the 2 core signals (pattern is already confirmed)
        all_signals = signals_met >= 1

        # Add score to signals for debugging
        signals["score"] = signal_score
        signals["max_score"] = total_weight
        signals["signals_met"] = signals_met + 1  # +1 for the mandatory pattern

        self.logger.debug(
            f"SHORT ENTRY: Pattern ✓ + {signals_met}/{len(core_signals)} other signals"
        )
        self.logger.debug(
            f"  Score: {signal_score:.2f}/{total_weight:.2f} ({signal_score / total_weight * 100:.1f}%)"
        )
        self.logger.debug(
            f"SHORT ENTRY RESULT: {'✅ SUFFICIENT SIGNALS' if all_signals else '❌ INSUFFICIENT SIGNALS'}"
        )
        if not all_signals:
            missing = [k for k in core_signals if not signals[k]]
            self.logger.debug(f"  Missing signals: {', '.join(missing)}")

        return all_signals, signals

    async def _check_bullish_pattern(self) -> bool:
        data_5m = await self.suite.data.get_data("5min", bars=120)
        if data_5m is None or len(data_5m) < 120:
            self.logger.debug("  Pattern check: Insufficient 5min data")
            return False

        data_5m = data_5m.pipe(FVG, min_gap_size=self.fvg_min_gap_size, check_mitigation=True).pipe(
            ORDERBLOCK, min_volume_percentile=self.ob_volume_percentile
        )

        last_row = data_5m.tail(1)
        data_15s = await self.suite.data.get_data("15sec")
        if data_15s is None:
            return False
        current_price = data_15s.tail(1)["close"][0]

        has_bullish_ob = False
        if (
            "ob_bullish" in last_row.columns
            and last_row["ob_bullish"][0]
            and "ob_bottom" in last_row.columns
        ):
            ob_bottom = last_row["ob_bottom"][0]
            if ob_bottom is not None:
                has_bullish_ob = current_price >= ob_bottom
                self.logger.debug(
                    f"  Bullish OB: Found at {ob_bottom:.2f}, price={current_price:.2f}, valid={has_bullish_ob}"
                )

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
        self.logger.debug(
            f"  Pattern result: OB={has_bullish_ob}, FVG={has_fvg_fill}, Final={result}"
        )
        return result

    async def _check_bearish_pattern(self) -> bool:
        data_5m = await self.suite.data.get_data("5min", bars=120)
        if data_5m is None or len(data_5m) < 120:
            self.logger.debug("  Pattern check: Insufficient 5min data")
            return False

        data_5m = data_5m.pipe(FVG, min_gap_size=self.fvg_min_gap_size, check_mitigation=True).pipe(
            ORDERBLOCK, min_volume_percentile=self.ob_volume_percentile
        )

        last_row = data_5m.tail(1)
        data_15s = await self.suite.data.get_data("15sec")
        if data_15s is None:
            return False
        current_price = data_15s.tail(1)["close"][0]

        has_bearish_ob = False
        if (
            "ob_bearish" in last_row.columns
            and last_row["ob_bearish"][0]
            and "ob_top" in last_row.columns
        ):
            ob_top = last_row["ob_top"][0]
            if ob_top is not None:
                has_bearish_ob = current_price <= ob_top
                self.logger.debug(
                    f"  Bearish OB: Found at {ob_top:.2f}, price={current_price:.2f}, valid={has_bearish_ob}"
                )

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
        self.logger.debug(
            f"  Pattern result: OB={has_bearish_ob}, FVG={has_fvg_fill}, Final={result}"
        )
        return result

    async def get_microstructure_score(self) -> float:
        """Calculate microstructure score based on WAE strength and price momentum."""
        data_15s = await self.suite.data.get_data("15sec", bars=120)
        if data_15s is None or len(data_15s) < 100:
            return 0.0

        data_15s = data_15s.pipe(WAE, sensitivity=self.wae_sensitivity)

        price_values = data_15s.select(pl.col("close").tail(5))["close"]
        if len(price_values) < 5:
            return 0.0

        # Calculate price momentum
        price_trend = (price_values[-1] - price_values[0]) / price_values[0]

        # Get WAE strength
        wae_strength = data_15s.tail(1)["wae_explosion"][0] / self.wae_sensitivity

        # Combined score based on price momentum and WAE strength
        return float(abs(price_trend) * wae_strength * 10)

    async def detect_entry_signal(self) -> tuple[int, dict]:
        """
        Detect entry signals for both long and short positions.

        Returns:
            Tuple of (signal_type, signals_dict) where:
            - signal_type: 0 = no signal, 1 = long, -1 = short
            - signals_dict: Dictionary with signal details
        """
        # Check for long entry
        long_signal, long_details = await self.check_long_entry()
        if long_signal:
            self.logger.info("Long entry signal detected")
            return 1, long_details

        # Check for short entry
        short_signal, short_details = await self.check_short_entry()
        if short_signal:
            self.logger.info("Short entry signal detected")
            return -1, short_details

        return 0, {}
