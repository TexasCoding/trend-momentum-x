import logging
from typing import Any

from project_x_py import TradingSuite

from utils import Config


class OrderBookAnalyzer:
    def __init__(self, suite: TradingSuite):
        self.suite = suite
        self.logger = logging.getLogger(__name__)
        self.imbalance_long_threshold = Config.IMBALANCE_LONG_THRESHOLD
        self.imbalance_short_threshold = Config.IMBALANCE_SHORT_THRESHOLD
        self.iceberg_check_enabled = Config.ICEBERG_CHECK
        self.depth_levels = Config.IMBALANCE_DEPTH_LEVELS

    async def get_market_imbalance(self) -> float | None:
        if not hasattr(self.suite, 'orderbook') or self.suite.orderbook is None:
            self.logger.debug("OrderBook not available")
            return None

        try:
            result = await self.suite.orderbook.get_market_imbalance(levels=self.depth_levels)
            if result and 'depth_imbalance' in result:
                imbalance = float(result['depth_imbalance'])
                self.logger.debug(f"Market imbalance: {imbalance:.4f} (levels={self.depth_levels})")
                return imbalance
            self.logger.debug("No imbalance data in result")
            return None
        except Exception as e:
            self.logger.debug(f"Error getting market imbalance: {e}")
            return None

    async def detect_icebergs(self) -> list[dict[str, Any]]:
        if not hasattr(self.suite, 'orderbook') or self.suite.orderbook is None:
            self.logger.debug("OrderBook not available for iceberg detection")
            return []

        try:
            # detect_iceberg_orders returns dict with 'iceberg_levels' key
            result = await self.suite.orderbook.detect_iceberg_orders()
            if result and 'iceberg_levels' in result:
                icebergs = list(result['iceberg_levels'])
                self.logger.debug(f"Detected {len(icebergs)} potential iceberg orders")
                for ice in icebergs:
                    self.logger.debug(f"  Iceberg: side={ice.get('side')}, price={ice.get('price')}, size={ice.get('size')}")
                return icebergs
            self.logger.debug("No iceberg orders detected")
            return []
        except Exception as e:
            self.logger.debug(f"Error detecting icebergs: {e}")
            return []

    async def confirm_long_entry(self) -> tuple[bool, dict[str, Any]]:
        self.logger.debug("="*60)
        self.logger.debug("ORDERBOOK CONFIRMATION - LONG ENTRY")

        confirmation: dict[str, Any] = {
            "imbalance": None,
            "icebergs": [],
            "confirmed": False,
            "reason": ""
        }

        imbalance = await self.get_market_imbalance()
        if imbalance is None:
            confirmation["reason"] = "OrderBook data unavailable"
            self.logger.debug(f"  ❌ {confirmation['reason']}")
            return False, confirmation

        confirmation["imbalance"] = imbalance

        # For long entry, we want bid volume > ask volume (imbalance > threshold)
        self.logger.debug(f"  Imbalance: {imbalance:.4f} (threshold: >{self.imbalance_long_threshold})")
        if imbalance < self.imbalance_long_threshold:
            confirmation["reason"] = f"Insufficient bid imbalance: {imbalance:.2f} < {self.imbalance_long_threshold}"
            self.logger.debug(f"  ❌ {confirmation['reason']}")
            return False, confirmation
        self.logger.debug("  ✓ Bid imbalance sufficient")

        if self.iceberg_check_enabled:
            icebergs = await self.detect_icebergs()
            confirmation["icebergs"] = icebergs

            ask_icebergs = [ice for ice in icebergs if ice.get('side') == 'ask']
            if ask_icebergs:
                confirmation["reason"] = f"Detected {len(ask_icebergs)} iceberg orders on ask side"
                self.logger.debug(f"  ❌ {confirmation['reason']}")
                return False, confirmation
            self.logger.debug("  ✓ No problematic iceberg orders")

        confirmation["confirmed"] = True
        confirmation["reason"] = f"Long entry confirmed with imbalance {imbalance:.2f}"
        self.logger.debug(f"  ✅ {confirmation['reason']}")
        return True, confirmation

    async def confirm_short_entry(self) -> tuple[bool, dict[str, Any]]:
        self.logger.debug("="*60)
        self.logger.debug("ORDERBOOK CONFIRMATION - SHORT ENTRY")

        confirmation: dict[str, Any] = {
            "imbalance": None,
            "icebergs": [],
            "confirmed": False,
            "reason": ""
        }

        imbalance = await self.get_market_imbalance()
        if imbalance is None:
            confirmation["reason"] = "OrderBook data unavailable"
            self.logger.debug(f"  ❌ {confirmation['reason']}")
            return False, confirmation

        confirmation["imbalance"] = imbalance

        # For short entry, we want ask volume > bid volume (imbalance < threshold)
        self.logger.debug(f"  Imbalance: {imbalance:.4f} (threshold: <{self.imbalance_short_threshold})")
        if imbalance > self.imbalance_short_threshold:
            confirmation["reason"] = f"Insufficient ask imbalance: {imbalance:.2f} > {self.imbalance_short_threshold}"
            self.logger.debug(f"  ❌ {confirmation['reason']}")
            return False, confirmation
        self.logger.debug("  ✓ Ask imbalance sufficient")

        if self.iceberg_check_enabled:
            icebergs = await self.detect_icebergs()
            confirmation["icebergs"] = icebergs

            bid_icebergs = [ice for ice in icebergs if ice.get('side') == 'bid']
            if bid_icebergs:
                confirmation["reason"] = f"Detected {len(bid_icebergs)} iceberg orders on bid side"
                self.logger.debug(f"  ❌ {confirmation['reason']}")
                return False, confirmation
            self.logger.debug("  ✓ No problematic iceberg orders")

        confirmation["confirmed"] = True
        confirmation["reason"] = f"Short entry confirmed with imbalance {imbalance:.2f}"
        self.logger.debug(f"  ✅ {confirmation['reason']}")
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
            # bids and asks are lists of PriceLevelDict with 'price' and 'volume' keys
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
