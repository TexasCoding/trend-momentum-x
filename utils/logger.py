import logging
import sys
from datetime import datetime


def setup_logger(name: str = "TrendMomentumX", level: str = "INFO") -> logging.Logger:
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    log_level = getattr(logging, level.upper())
    logger.setLevel(log_level)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)

    file_handler = logging.FileHandler(
        f"trading_{datetime.now().strftime('%Y%m%d')}.log"
    )
    file_handler.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    console_handler.setFormatter(formatter)
    file_handler.setFormatter(formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    # Configure strategy module loggers to use same handlers
    configure_strategy_logging(log_level, console_handler, file_handler)

    # Configure project-x-py loggers to show warnings and errors
    configure_project_x_logging(log_level, file_handler)

    return logger


def configure_strategy_logging(log_level: int, console_handler: logging.StreamHandler, file_handler: logging.FileHandler) -> None:
    """Configure strategy module loggers to use the same handlers as main logger."""
    # List of strategy modules that need logging
    strategy_modules = [
        "strategy.trend_analysis",
        "strategy.signals",
        "strategy.orderbook",
        "strategy.exits",
        "strategy.risk_manager",
    ]

    # Configure each module's logger
    for module_name in strategy_modules:
        module_logger = logging.getLogger(module_name)
        module_logger.setLevel(log_level)

        # Clear existing handlers to avoid duplicates
        module_logger.handlers.clear()

        # Add the same handlers as main logger
        module_logger.addHandler(console_handler)
        module_logger.addHandler(file_handler)

        # Don't propagate to avoid duplicate logs
        module_logger.propagate = False


def configure_project_x_logging(log_level: int, file_handler: logging.FileHandler) -> None:
    """Configure project-x-py library loggers to capture warnings and errors."""
    # List of project-x-py modules that should have logging enabled
    px_modules = [
        "project_x_py",
        "project_x_py.realtime",
        "project_x_py.realtime_data_manager",
        "project_x_py.event_bus",
        "project_x_py.trading_suite",
        "project_x_py.order_manager",
        "project_x_py.position_manager",
        "project_x_py.risk_manager",
        "project_x_py.orderbook",
    ]

    # Set up logging for each module
    for module_name in px_modules:
        module_logger = logging.getLogger(module_name)
        # Show warnings and errors from project-x-py
        module_logger.setLevel(logging.WARNING)

        # Clear existing handlers to avoid duplicates
        module_logger.handlers.clear()

        # Add file handler to capture all project-x-py logs
        module_logger.addHandler(file_handler)

        # Add console handler only for errors to avoid cluttering output
        error_console_handler = logging.StreamHandler(sys.stdout)
        error_console_handler.setLevel(logging.ERROR)
        error_formatter = logging.Formatter(
            '%(asctime)s - [PROJECT-X-PY] %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        error_console_handler.setFormatter(error_formatter)
        module_logger.addHandler(error_console_handler)

        # Don't propagate to avoid duplicate logs
        module_logger.propagate = False

    # If debug mode is enabled, show more verbose project-x-py logs
    if log_level <= logging.DEBUG:
        for module_name in px_modules:
            logging.getLogger(module_name).setLevel(logging.DEBUG)
