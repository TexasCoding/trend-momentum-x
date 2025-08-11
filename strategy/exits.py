import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

from project_x_py import TradingSuite
from project_x_py.indicators import SAR

from utils import Config


class ExitManager:
    def __init__(self, suite: TradingSuite):
        self.suite = suite
        self.logger = logging.getLogger(__name__)
        self.time_exit_minutes = Config.TIME_EXIT_MINUTES
        self.breakeven_trigger_ratio = Config.BREAKEVEN_TRIGGER_RATIO
        self.breakeven_offset_ticks = Config.BREAKEVEN_OFFSET_TICKS
        self.sar_af = Config.SAR_AF
        self.sar_max_af = Config.SAR_MAX_AF
        self.trailing_enabled = True
        self.active_positions: dict[str, dict[str, Any]] = {}

    async def manage_position(self, position: dict):
        position_id = position.get("id")
        if not position_id:
            return

        self.active_positions[position_id] = {
            "entry_time": datetime.now(),
            "entry_price": position.get("entry_price"),
            "stop_price": position.get("stop_price"),
            "target_price": position.get("target_price"),
            "direction": position.get("direction"),
            "size": position.get("size"),
            "trailing_stop_activated": False,
            "breakeven_activated": False,
        }

        self.logger.debug(f"Managing position {position_id}: {position.get('direction')} @ {position.get('entry_price'):.2f}")
        self.logger.debug(f"  Stop: {position.get('stop_price'):.2f}, Target: {position.get('target_price'):.2f}")

        while position_id in self.active_positions:
            exit_signal = await self._check_exit_conditions(position_id)

            if exit_signal["should_exit"]:
                self.logger.info(f"Exit signal for {position_id}: {exit_signal['reason']}")
                await self._exit_position(position_id, exit_signal["reason"])
                break

            if (
                self.trailing_enabled
                and not self.active_positions[position_id]["trailing_stop_activated"]
            ):
                await self._check_trailing_activation(position_id)

            if self.active_positions[position_id]["trailing_stop_activated"]:
                await self._update_trailing_stop(position_id)

            await asyncio.sleep(1)

    async def _check_exit_conditions(self, position_id: str) -> dict:
        position = self.active_positions.get(position_id)
        if not position:
            return {"should_exit": False, "reason": ""}

        current_price = await self.suite.data.get_current_price()
        if not current_price:
            return {"should_exit": False, "reason": ""}

        # Check target and stop
        if position["direction"] == "long":
            pnl = current_price - position["entry_price"]
            if current_price >= position["target_price"]:
                self.logger.debug(f"Position {position_id}: Target reached ({current_price:.2f} >= {position['target_price']:.2f})")
                return {"should_exit": True, "reason": "Target reached"}
            if current_price <= position["stop_price"]:
                self.logger.debug(f"Position {position_id}: Stop hit ({current_price:.2f} <= {position['stop_price']:.2f})")
                return {"should_exit": True, "reason": "Stop loss hit"}
        else:
            pnl = position["entry_price"] - current_price
            if current_price <= position["target_price"]:
                self.logger.debug(f"Position {position_id}: Target reached ({current_price:.2f} <= {position['target_price']:.2f})")
                return {"should_exit": True, "reason": "Target reached"}
            if current_price >= position["stop_price"]:
                self.logger.debug(f"Position {position_id}: Stop hit ({current_price:.2f} >= {position['stop_price']:.2f})")
                return {"should_exit": True, "reason": "Stop loss hit"}

        # Check time exit
        time_elapsed = datetime.now() - position["entry_time"]
        if time_elapsed > timedelta(minutes=self.time_exit_minutes):
            entry_price = position["entry_price"]
            if position["direction"] == "long":
                if current_price <= entry_price:
                    self.logger.debug(f"Position {position_id}: Time exit - no progress after {self.time_exit_minutes} min")
                    return {"should_exit": True, "reason": "Time exit - no progress"}
            else:
                if current_price >= entry_price:
                    self.logger.debug(f"Position {position_id}: Time exit - no progress after {self.time_exit_minutes} min")
                    return {"should_exit": True, "reason": "Time exit - no progress"}

        # Check trend reversal
        trend_reversed = await self._check_trend_reversal(position["direction"])
        if trend_reversed:
            self.logger.debug(f"Position {position_id}: Trend reversal detected")
            return {"should_exit": True, "reason": "Trend reversal detected"}

        return {"should_exit": False, "reason": ""}

    async def _check_trend_reversal(self, position_direction: str) -> bool:
        # Avoid circular import by directly checking trend here
        data_5m = await self.suite.data.get_data("5min", bars=50)
        if data_5m is None or len(data_5m) < 35:  # Need enough for MACD calculation
            return False

        from project_x_py.indicators import MACD

        data_5m = data_5m.pipe(MACD, fast_period=12, slow_period=26, signal_period=9)

        hist_last = data_5m.tail(1)["macd_histogram"][0]
        self.logger.debug(f"MACD Histogram for trend reversal check: {hist_last:.4f}")

        reversal = (
            position_direction == "long" and hist_last < -0.01
            or position_direction == "short" and hist_last > 0.01
        )

        if reversal:
            self.logger.debug(f"Trend reversal confirmed: {position_direction} position with MACD hist={hist_last:.4f}")

        return reversal

    async def _check_trailing_activation(self, position_id: str):
        position = self.active_positions.get(position_id)
        if not position:
            return

        current_price = await self.suite.data.get_current_price()
        if not current_price:
            return

        entry_price = position["entry_price"]
        stop_price = position["stop_price"]
        risk_amount = abs(entry_price - stop_price)
        breakeven_trigger = risk_amount * self.breakeven_trigger_ratio

        if position["direction"] == "long":
            profit = current_price - entry_price
            if current_price >= entry_price + breakeven_trigger:
                self.logger.debug(f"Position {position_id}: Profit {profit:.2f} >= trigger {breakeven_trigger:.2f}")
                if not position["breakeven_activated"]:
                    self.logger.info(f"Position {position_id}: Moving stop to breakeven")
                    await self._move_stop_to_breakeven(position_id)
                position["trailing_stop_activated"] = True
                self.logger.debug(f"Position {position_id}: Trailing stop activated")
        else:
            profit = entry_price - current_price
            if current_price <= entry_price - breakeven_trigger:
                self.logger.debug(f"Position {position_id}: Profit {profit:.2f} >= trigger {breakeven_trigger:.2f}")
                if not position["breakeven_activated"]:
                    self.logger.info(f"Position {position_id}: Moving stop to breakeven")
                    await self._move_stop_to_breakeven(position_id)
                position["trailing_stop_activated"] = True
                self.logger.debug(f"Position {position_id}: Trailing stop activated")

    async def _move_stop_to_breakeven(self, position_id: str):
        position = self.active_positions.get(position_id)
        if not position:
            return

        instrument = self.suite.instrument
        if not instrument or not hasattr(instrument, "tickSize"):
            return

        tick_size = instrument.tickSize
        offset = self.breakeven_offset_ticks * tick_size

        entry_price = position["entry_price"]

        new_stop = entry_price + offset if position["direction"] == "long" else entry_price - offset

        try:
            # Modify stop loss order
            await self.suite.orders.modify_order(position_id, stop_loss_price=new_stop)
            position["stop_price"] = new_stop
            position["breakeven_activated"] = True
            self.logger.info(f"Moved stop to breakeven for {position_id} at {new_stop:.2f}")
        except Exception as e:
            # Fallback: try to cancel and replace the order if modify isn't supported
            try:
                await self.suite.orders.cancel_order(position_id + "_stop")
                await self.suite.orders.place_stop_order(
                    contract_id=str(self.suite.instrument.id) if self.suite.instrument else "0",
                    side=1 if position["direction"] == "long" else 0,  # Opposite side for stop
                    size=position["size"],
                    stop_price=new_stop,
                )
                position["stop_price"] = new_stop
                position["breakeven_activated"] = True
                self.logger.info(f"Moved stop to breakeven (fallback) for {position_id} at {new_stop:.2f}")
            except Exception as e2:
                self.logger.error(f"Failed to move stop to breakeven: {e} | Fallback failed: {e2}")

    async def _update_trailing_stop(self, position_id: str):
        position = self.active_positions.get(position_id)
        if not position:
            return

        data_15s = await self.suite.data.get_data("15sec", bars=20)
        if data_15s is None or len(data_15s) < 10:
            return

        # SAR indicator - uses configured parameters
        data_15s = data_15s.pipe(SAR, acceleration=self.sar_af, maximum=self.sar_max_af)
        current_sar = data_15s.tail(1)["SAR"][0]

        current_price = await self.suite.data.get_current_price()
        if not current_price:
            return

        if position["direction"] == "long":
            if current_sar > position["stop_price"] and current_sar < current_price:
                old_stop = position["stop_price"]
                try:
                    await self.suite.orders.modify_order(position_id, stop_loss_price=current_sar)
                    position["stop_price"] = current_sar
                    self.logger.debug(f"Position {position_id}: Trailing stop updated {old_stop:.2f} -> {current_sar:.2f}")
                except Exception as e:
                    self.logger.error(f"Failed to update trailing stop: {e}")
        else:
            if current_sar < position["stop_price"] and current_sar > current_price:
                old_stop = position["stop_price"]
                try:
                    await self.suite.orders.modify_order(position_id, stop_loss_price=current_sar)
                    position["stop_price"] = current_sar
                    self.logger.debug(f"Position {position_id}: Trailing stop updated {old_stop:.2f} -> {current_sar:.2f}")
                except Exception as e:
                    self.logger.error(f"Failed to update trailing stop: {e}")

    async def _exit_position(self, position_id: str, reason: str):
        try:
            await self.suite.orders.close_position(position_id)
            self.logger.info(f"Position {position_id} closed: {reason}")
            del self.active_positions[position_id]
        except Exception as e:
            self.logger.error(f"Failed to close position {position_id}: {e}")

    def get_active_positions(self) -> dict:
        return self.active_positions
