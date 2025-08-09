from typing import Any

from project_x_py import TradingSuite


class OrderBookAnalyzer:
    def __init__(self, suite: TradingSuite):
        self.suite = suite
        self.imbalance_long_threshold = 1.5
        self.imbalance_short_threshold = 0.6667
        self.depth_levels = 5
        self.iceberg_check_enabled = True

    async def get_market_imbalance(self) -> float | None:
        if not hasattr(self.suite, 'orderbook') or self.suite.orderbook is None:
            return None

        try:
            # get_market_imbalance returns LiquidityAnalysisResponse object
            result = await self.suite.orderbook.get_market_imbalance(levels=self.depth_levels)
            if result and hasattr(result, 'depth_imbalance'):
                return float(result.depth_imbalance)
            return None
        except Exception:
            return None

    async def detect_icebergs(self) -> list[dict[str, Any]]:
        if not hasattr(self.suite, 'orderbook') or self.suite.orderbook is None:
            return []

        try:
            # detect_iceberg_orders returns dict with 'iceberg_levels' key
            result = await self.suite.orderbook.detect_iceberg_orders()
            if result and 'iceberg_levels' in result:
                return list(result['iceberg_levels'])
            return []
        except Exception:
            return []

    async def confirm_long_entry(self) -> tuple[bool, dict[str, Any]]:
        confirmation: dict[str, Any] = {
            "imbalance": None,
            "icebergs": [],
            "confirmed": False,
            "reason": ""
        }

        imbalance = await self.get_market_imbalance()
        if imbalance is None:
            confirmation["reason"] = "OrderBook data unavailable"
            return False, confirmation

        confirmation["imbalance"] = imbalance

        # For long entry, we want bid volume > ask volume (imbalance > threshold)
        if imbalance < self.imbalance_long_threshold:
            confirmation["reason"] = f"Insufficient bid imbalance: {imbalance:.2f} < {self.imbalance_long_threshold}"
            return False, confirmation

        if self.iceberg_check_enabled:
            icebergs = await self.detect_icebergs()
            confirmation["icebergs"] = icebergs

            ask_icebergs = [ice for ice in icebergs if ice.get('side') == 'ask']
            if ask_icebergs:
                confirmation["reason"] = f"Detected {len(ask_icebergs)} iceberg orders on ask side"
                return False, confirmation

        confirmation["confirmed"] = True
        confirmation["reason"] = f"Long entry confirmed with imbalance {imbalance:.2f}"
        return True, confirmation

    async def confirm_short_entry(self) -> tuple[bool, dict[str, Any]]:
        confirmation: dict[str, Any] = {
            "imbalance": None,
            "icebergs": [],
            "confirmed": False,
            "reason": ""
        }

        imbalance = await self.get_market_imbalance()
        if imbalance is None:
            confirmation["reason"] = "OrderBook data unavailable"
            return False, confirmation

        confirmation["imbalance"] = imbalance

        # For short entry, we want ask volume > bid volume (imbalance < threshold)
        if imbalance > self.imbalance_short_threshold:
            confirmation["reason"] = f"Insufficient ask imbalance: {imbalance:.2f} > {self.imbalance_short_threshold}"
            return False, confirmation

        if self.iceberg_check_enabled:
            icebergs = await self.detect_icebergs()
            confirmation["icebergs"] = icebergs

            bid_icebergs = [ice for ice in icebergs if ice.get('side') == 'bid']
            if bid_icebergs:
                confirmation["reason"] = f"Detected {len(bid_icebergs)} iceberg orders on bid side"
                return False, confirmation

        confirmation["confirmed"] = True
        confirmation["reason"] = f"Short entry confirmed with imbalance {imbalance:.2f}"
        return True, confirmation

    async def get_orderbook_pressure(self) -> dict[str, Any]:
        if not hasattr(self.suite, 'orderbook') or self.suite.orderbook is None:
            return {"bid_pressure": 0, "ask_pressure": 0, "net_pressure": 0}

        try:
            # Use get_orderbook_snapshot to get current state
            snapshot = await self.suite.orderbook.get_orderbook_snapshot(levels=self.depth_levels)
            if not snapshot:
                return {"bid_pressure": 0, "ask_pressure": 0, "net_pressure": 0}

            # Calculate volumes from snapshot
            bid_volume = sum(level["volume"] for level in snapshot.get("bids", []))
            ask_volume = sum(level["volume"] for level in snapshot.get("asks", []))

            total_volume = bid_volume + ask_volume
            if total_volume == 0:
                return {"bid_pressure": 0, "ask_pressure": 0, "net_pressure": 0}

            bid_pressure = bid_volume / total_volume
            ask_pressure = ask_volume / total_volume
            net_pressure = bid_pressure - ask_pressure

            return {
                "bid_pressure": bid_pressure,
                "ask_pressure": ask_pressure,
                "net_pressure": net_pressure,
                "bid_volume": bid_volume,
                "ask_volume": ask_volume
            }
        except Exception:
            return {"bid_pressure": 0, "ask_pressure": 0, "net_pressure": 0}
