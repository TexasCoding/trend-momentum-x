import asyncio
from datetime import datetime, timedelta
from typing import Any

from project_x_py import TradingSuite
from project_x_py.indicators import SAR


class ExitManager:
    def __init__(self, suite: TradingSuite):
        self.suite = suite
        self.time_exit_minutes = 5
        self.breakeven_trigger_ratio = 1.0
        self.breakeven_offset_ticks = 5
        self.sar_af = 0.02
        self.sar_max_af = 0.2
        self.sar_step = 0.02  # Add missing sar_step attribute
        self.trailing_enabled = True
        self.active_positions: dict[str, dict[str, Any]] = {}

    async def manage_position(self, position: dict):
        position_id = position.get('id')
        if not position_id:
            return

        self.active_positions[position_id] = {
            'entry_time': datetime.now(),
            'entry_price': position.get('entry_price'),
            'stop_price': position.get('stop_price'),
            'target_price': position.get('target_price'),
            'direction': position.get('direction'),
            'size': position.get('size'),
            'trailing_stop_activated': False,
            'breakeven_activated': False
        }

        while position_id in self.active_positions:
            exit_signal = await self._check_exit_conditions(position_id)

            if exit_signal['should_exit']:
                await self._exit_position(position_id, exit_signal['reason'])
                break

            if self.trailing_enabled and not self.active_positions[position_id]['trailing_stop_activated']:
                await self._check_trailing_activation(position_id)

            if self.active_positions[position_id]['trailing_stop_activated']:
                await self._update_trailing_stop(position_id)

            await asyncio.sleep(1)

    async def _check_exit_conditions(self, position_id: str) -> dict:
        position = self.active_positions.get(position_id)
        if not position:
            return {'should_exit': False, 'reason': ''}

        current_price = await self.suite.data.get_current_price()
        if not current_price:
            return {'should_exit': False, 'reason': ''}

        if position['direction'] == 'long':
            if current_price >= position['target_price']:
                return {'should_exit': True, 'reason': 'Target reached'}
            if current_price <= position['stop_price']:
                return {'should_exit': True, 'reason': 'Stop loss hit'}
        else:
            if current_price <= position['target_price']:
                return {'should_exit': True, 'reason': 'Target reached'}
            if current_price >= position['stop_price']:
                return {'should_exit': True, 'reason': 'Stop loss hit'}

        time_elapsed = datetime.now() - position['entry_time']
        if time_elapsed > timedelta(minutes=self.time_exit_minutes):
            entry_price = position['entry_price']
            if position['direction'] == 'long':
                if current_price <= entry_price:
                    return {'should_exit': True, 'reason': 'Time exit - no progress'}
            else:
                if current_price >= entry_price:
                    return {'should_exit': True, 'reason': 'Time exit - no progress'}

        trend_reversed = await self._check_trend_reversal(position['direction'])
        if trend_reversed:
            return {'should_exit': True, 'reason': 'Trend reversal detected'}

        return {'should_exit': False, 'reason': ''}

    async def _check_trend_reversal(self, position_direction: str) -> bool:
        from .trend_analysis import TrendAnalyzer
        trend_analyzer = TrendAnalyzer(self.suite)

        current_trend = await trend_analyzer.get_5min_trend()

        return bool(position_direction == 'long' and current_trend == 'bearish' or position_direction == 'short' and current_trend == 'bullish')

    async def _check_trailing_activation(self, position_id: str):
        position = self.active_positions.get(position_id)
        if not position:
            return

        current_price = await self.suite.data.get_current_price()
        if not current_price:
            return

        entry_price = position['entry_price']
        stop_price = position['stop_price']
        risk_amount = abs(entry_price - stop_price)
        breakeven_trigger = risk_amount * self.breakeven_trigger_ratio

        if position['direction'] == 'long':
            if current_price >= entry_price + breakeven_trigger:
                if not position['breakeven_activated']:
                    await self._move_stop_to_breakeven(position_id)
                position['trailing_stop_activated'] = True
        else:
            if current_price <= entry_price - breakeven_trigger:
                if not position['breakeven_activated']:
                    await self._move_stop_to_breakeven(position_id)
                position['trailing_stop_activated'] = True

    async def _move_stop_to_breakeven(self, position_id: str):
        position = self.active_positions.get(position_id)
        if not position:
            return

        instrument = self.suite.instrument
        if not instrument or not hasattr(instrument, 'tickSize'):
            return

        tick_size = instrument.tickSize
        offset = self.breakeven_offset_ticks * tick_size

        entry_price = position['entry_price']

        new_stop = entry_price + offset if position['direction'] == 'long' else entry_price - offset

        try:
            # Modify stop loss - API depends on project_x_py implementation
            # await self.suite.orders.modify_order(position_id, stop_loss_price=new_stop)
            pass  # TODO: Implement when API is confirmed
            position['stop_price'] = new_stop
            position['breakeven_activated'] = True
        except Exception as e:
            print(f"Failed to move stop to breakeven: {e}")

    async def _update_trailing_stop(self, position_id: str):
        position = self.active_positions.get(position_id)
        if not position:
            return

        data_15s = await self.suite.data.get_data("15s")
        if data_15s is None or len(data_15s) < 10:
            return

        # SAR indicator - uses default parameters
        data_15s = data_15s.pipe(SAR)
        current_sar = data_15s.tail(1)["SAR"][0]

        current_price = await self.suite.data.get_current_price()
        if not current_price:
            return

        if position['direction'] == 'long':
            if current_sar > position['stop_price'] and current_sar < current_price:
                try:
                    await self.suite.orders.modify_order(position_id, stop_loss_price=current_sar)
                    position['stop_price'] = current_sar
                except Exception as e:
                    print(f"Failed to update trailing stop: {e}")
        else:
            if current_sar < position['stop_price'] and current_sar > current_price:
                try:
                    await self.suite.orders.modify_order(position_id, stop_loss_price=current_sar)
                    position['stop_price'] = current_sar
                except Exception as e:
                    print(f"Failed to update trailing stop: {e}")

    async def _exit_position(self, position_id: str, reason: str):
        try:
            await self.suite.orders.close_position(position_id)
            print(f"Position {position_id} closed: {reason}")
            del self.active_positions[position_id]
        except Exception as e:
            print(f"Failed to close position {position_id}: {e}")

    def get_active_positions(self) -> dict:
        return self.active_positions
