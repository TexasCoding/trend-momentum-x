
from typing import Any

from project_x_py import TradingSuite
from project_x_py.indicators import ATR


class RiskManager:
    def __init__(self, suite: TradingSuite):
        self.suite = suite
        self.risk_per_trade = 0.005  # 0.5% per trade
        self.max_daily_loss = 0.03  # 3% daily loss limit
        self.max_weekly_loss = 0.05  # 5% weekly loss limit
        self.rr_ratio = 2  # Risk:Reward ratio
        self.max_concurrent_trades = 3
        self.correlation_threshold = 0.8
        self.atr_period = 14
        self.stop_ticks = 10  # Default stop in ticks
        self.daily_pnl = 0.0
        self.weekly_pnl = 0.0
        self.open_positions: list[dict[str, Any]] = []

    async def calculate_position_size(self, entry_price: float, stop_price: float) -> int | None:
        account_info = self.suite.client.get_account_info()
        if not account_info:
            return None

        balance = account_info.balance if hasattr(account_info, 'balance') else 0
        if balance <= 0:
            return None

        risk_amount = self.risk_per_trade * balance

        instrument = self.suite.instrument
        if not instrument or not hasattr(instrument, 'tickValue'):
            return None

        tick_value = instrument.tickValue
        tick_size = instrument.tickSize

        if not tick_value or not tick_size:
            return None

        stop_distance_dollars = abs(entry_price - stop_price)
        stop_distance_ticks = stop_distance_dollars / tick_size
        risk_per_contract = stop_distance_ticks * tick_value

        if risk_per_contract <= 0:
            return None

        position_size = int(risk_amount / risk_per_contract)

        position_size = min(position_size, self._get_max_position_size())

        return max(1, position_size)

    async def calculate_stop_price(self, entry_price: float, direction: str) -> float:
        data_1m = await self.suite.data.get_data("1min")
        if data_1m is not None and len(data_1m) >= self.atr_period:
            data_1m = data_1m.pipe(ATR, period=self.atr_period)
            atr_value = data_1m.tail(1)["ATR_14"][0]

            stop_price = entry_price - atr_value if direction == "long" else entry_price + atr_value
        else:
            instrument = self.suite.instrument
            if instrument and hasattr(instrument, 'tickSize'):
                tick_size = instrument.tickSize
                stop_distance = self.stop_ticks * tick_size

                if direction == "long":
                    stop_price = entry_price - stop_distance
                else:
                    stop_price = entry_price + stop_distance
            else:
                stop_distance = entry_price * 0.01

                if direction == "long":
                    stop_price = entry_price - stop_distance
                else:
                    stop_price = entry_price + stop_distance

        return stop_price

    def calculate_target_price(self, entry_price: float, stop_price: float, direction: str) -> float:
        stop_distance = abs(entry_price - stop_price)
        target_distance = stop_distance * self.rr_ratio

        if direction == "long":
            target_price = entry_price + target_distance
        else:
            target_price = entry_price - target_distance

        return target_price

    def can_trade(self) -> tuple[bool, str]:
        if self.daily_pnl <= -self.max_daily_loss:
            return False, f"Daily loss limit reached: {self.daily_pnl:.2%}"

        if self.weekly_pnl <= -self.max_weekly_loss:
            return False, f"Weekly loss limit reached: {self.weekly_pnl:.2%}"

        if len(self.open_positions) >= self.max_concurrent_trades:
            return False, f"Max concurrent trades reached: {len(self.open_positions)}"

        return True, "Trading allowed"

    def update_pnl(self, pnl: float):
        self.daily_pnl = float(self.daily_pnl + pnl)
        self.weekly_pnl = float(self.weekly_pnl + pnl)

    def reset_daily_pnl(self):
        self.daily_pnl = 0

    def reset_weekly_pnl(self):
        self.weekly_pnl = 0

    def add_position(self, position: dict):
        self.open_positions.append(position)

    def remove_position(self, position_id: str):
        self.open_positions = [p for p in self.open_positions if p.get('id') != position_id]

    def _get_max_position_size(self) -> int:
        # Default max position size
        # Can be adjusted based on instrument specifications
        return 10

    def get_risk_metrics(self) -> dict:
        return {
            "daily_pnl": self.daily_pnl,
            "weekly_pnl": self.weekly_pnl,
            "open_positions": len(self.open_positions),
            "max_positions": self.max_concurrent_trades,
            "risk_per_trade": self.risk_per_trade,
            "can_trade": self.can_trade()[0]
        }
