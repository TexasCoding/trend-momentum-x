import os
from typing import Any

from dotenv import load_dotenv

load_dotenv(dotenv_path=".env")


class Config:
    INSTRUMENT = os.getenv("TRADING_INSTRUMENT", "ES")
    TIMEFRAMES = ["15sec", "1min", "5min", "15min"]

    RISK_PER_TRADE = float(os.getenv("RISK_PER_TRADE", "0.005"))
    RR_RATIO = float(os.getenv("RR_RATIO", "2"))
    MAX_DAILY_LOSS = float(os.getenv("MAX_DAILY_LOSS", "0.03"))
    MAX_WEEKLY_LOSS = float(os.getenv("MAX_WEEKLY_LOSS", "0.05"))

    VOLUME_THRESHOLD_PERCENT = float(os.getenv("VOLUME_THRESHOLD", "0.2"))
    IMBALANCE_LONG_THRESHOLD = float(os.getenv("IMBALANCE_LONG", "1.5"))
    IMBALANCE_SHORT_THRESHOLD = float(os.getenv("IMBALANCE_SHORT", "0.6667"))
    ICEBERG_CHECK = os.getenv("ICEBERG_CHECK", "true").lower() == "true"

    EMA_FAST = int(os.getenv("EMA_FAST", "50"))
    EMA_SLOW = int(os.getenv("EMA_SLOW", "200"))
    MACD_FAST = int(os.getenv("MACD_FAST", "12"))
    MACD_SLOW = int(os.getenv("MACD_SLOW", "26"))
    MACD_SIGNAL = int(os.getenv("MACD_SIGNAL", "9"))

    RSI_PERIOD = int(os.getenv("RSI_PERIOD", "14"))
    RSI_OVERSOLD = int(os.getenv("RSI_OVERSOLD", "30"))
    RSI_OVERBOUGHT = int(os.getenv("RSI_OVERBOUGHT", "70"))
    RSI_LONG_CROSS = int(os.getenv("RSI_LONG_CROSS", "40"))
    RSI_SHORT_CROSS = int(os.getenv("RSI_SHORT_CROSS", "60"))

    WAE_SENSITIVITY = int(os.getenv("WAE_SENSITIVITY", "150"))

    SAR_AF = float(os.getenv("SAR_AF", "0.02"))
    SAR_MAX_AF = float(os.getenv("SAR_MAX_AF", "0.2"))

    TIME_EXIT_MINUTES = int(os.getenv("TIME_EXIT_MINUTES", "5"))
    BREAKEVEN_TRIGGER_RATIO = float(os.getenv("BREAKEVEN_TRIGGER", "1.0"))
    BREAKEVEN_OFFSET_TICKS = int(os.getenv("BREAKEVEN_OFFSET_TICKS", "5"))

    MAX_CONCURRENT_TRADES = int(os.getenv("MAX_CONCURRENT_TRADES", "3"))
    CORRELATION_THRESHOLD = float(os.getenv("CORRELATION_THRESHOLD", "0.8"))

    TRADING_MODE = os.getenv("TRADING_MODE", "paper")  # paper or live

    @classmethod
    def get_trading_suite_config(cls) -> dict[str, Any]:
        return {"features": ["orderbook", "risk_manager"], "timeframes": cls.TIMEFRAMES}

    @classmethod
    def get_all_settings(cls) -> dict[str, Any]:
        return {
            "instrument": cls.INSTRUMENT,
            "timeframes": cls.TIMEFRAMES,
            "risk": {
                "per_trade": cls.RISK_PER_TRADE,
                "rr_ratio": cls.RR_RATIO,
                "max_daily_loss": cls.MAX_DAILY_LOSS,
                "max_weekly_loss": cls.MAX_WEEKLY_LOSS,
                "max_concurrent": cls.MAX_CONCURRENT_TRADES,
            },
            "filters": {
                "volume_threshold": cls.VOLUME_THRESHOLD_PERCENT,
                "imbalance_long": cls.IMBALANCE_LONG_THRESHOLD,
                "imbalance_short": cls.IMBALANCE_SHORT_THRESHOLD,
                "iceberg_check": cls.ICEBERG_CHECK,
            },
            "indicators": {
                "ema": {"fast": cls.EMA_FAST, "slow": cls.EMA_SLOW},
                "macd": {"fast": cls.MACD_FAST, "slow": cls.MACD_SLOW, "signal": cls.MACD_SIGNAL},
                "rsi": {
                    "period": cls.RSI_PERIOD,
                    "oversold": cls.RSI_OVERSOLD,
                    "overbought": cls.RSI_OVERBOUGHT,
                },
                "wae": {"sensitivity": cls.WAE_SENSITIVITY},
                "sar": {"af": cls.SAR_AF, "max_af": cls.SAR_MAX_AF},
            },
            "exits": {
                "time_minutes": cls.TIME_EXIT_MINUTES,
                "breakeven_trigger": cls.BREAKEVEN_TRIGGER_RATIO,
                "breakeven_offset_ticks": cls.BREAKEVEN_OFFSET_TICKS,
            },
            "mode": cls.TRADING_MODE,
        }
