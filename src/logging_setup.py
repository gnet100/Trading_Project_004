"""
Trading Project 004 - Logging Setup Module
Configures logging for the entire application based on configuration settings.
"""

import logging
import logging.handlers
import os
import sys
from pathlib import Path
from typing import Dict, Any

# Add the parent directory to sys.path to import config_manager
sys.path.insert(0, str(Path(__file__).parent))
from config_manager import get_config


def parse_log_size(size_str: str) -> int:
    """
    Parse log file size string (e.g., '10MB', '1GB') to bytes
    
    Args:
        size_str: Size string like '10MB', '1GB', etc.
        
    Returns:
        Size in bytes
    """
    size_str = size_str.upper()
    
    if size_str.endswith('KB'):
        return int(size_str[:-2]) * 1024
    elif size_str.endswith('MB'):
        return int(size_str[:-2]) * 1024 * 1024
    elif size_str.endswith('GB'):
        return int(size_str[:-2]) * 1024 * 1024 * 1024
    else:
        # Assume bytes if no suffix
        return int(size_str)


def setup_logging() -> logging.Logger:
    """
    Set up logging configuration for the trading project
    
    Returns:
        Configured root logger
    """
    config = get_config()
    log_config = config.get_logging_config()
    
    # Create logs directory if it doesn't exist
    log_path = Path(log_config.file_path)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_config.level.upper()))
    
    # Clear existing handlers
    root_logger.handlers.clear()
    
    # Configure file handler if enabled
    if log_config.file_enabled:
        max_bytes = parse_log_size(log_config.file_max_size)
        file_handler = logging.handlers.RotatingFileHandler(
            log_config.file_path,
            maxBytes=max_bytes,
            backupCount=log_config.file_backup_count,
            encoding='utf-8'
        )
        file_formatter = logging.Formatter(log_config.file_format)
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)
    
    # Configure console handler if enabled
    if log_config.console_enabled:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, log_config.console_level.upper()))
        console_formatter = logging.Formatter(log_config.console_format)
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)
    
    # Configure module-specific log levels
    for module_name, level in log_config.module_levels.items():
        module_logger = logging.getLogger(module_name)
        module_logger.setLevel(getattr(logging, level.upper()))
    
    # Log the configuration
    logger = logging.getLogger(__name__)
    logger.info("Logging system initialized")
    logger.info(f"Log level: {log_config.level}")
    logger.info(f"File logging: {'enabled' if log_config.file_enabled else 'disabled'}")
    logger.info(f"Console logging: {'enabled' if log_config.console_enabled else 'disabled'}")
    
    return root_logger


def get_logger(name: str = None) -> logging.Logger:
    """
    Get a logger instance with the given name
    
    Args:
        name: Logger name (defaults to caller's module)
        
    Returns:
        Logger instance
    """
    if name is None:
        # Get the caller's module name
        frame = sys._getframe(1)
        name = frame.f_globals.get('__name__', 'unknown')
    
    return logging.getLogger(name)


class LoggerMixin:
    """Mixin class to add logging capabilities to any class"""
    
    @property
    def logger(self) -> logging.Logger:
        """Get logger for this class"""
        return get_logger(f"{self.__class__.__module__}.{self.__class__.__name__}")


def log_function_call(func):
    """Decorator to log function calls"""
    def wrapper(*args, **kwargs):
        logger = get_logger(func.__module__)
        logger.debug(f"Calling {func.__name__} with args={args}, kwargs={kwargs}")
        try:
            result = func(*args, **kwargs)
            logger.debug(f"{func.__name__} completed successfully")
            return result
        except Exception as e:
            logger.error(f"{func.__name__} failed: {e}")
            raise
    return wrapper


def log_execution_time(func):
    """Decorator to log function execution time"""
    import time
    
    def wrapper(*args, **kwargs):
        logger = get_logger(func.__module__)
        start_time = time.time()
        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            logger.info(f"{func.__name__} executed in {execution_time:.4f} seconds")
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"{func.__name__} failed after {execution_time:.4f} seconds: {e}")
            raise
    return wrapper


if __name__ == "__main__":
    # Test logging setup
    try:
        setup_logging()
        logger = get_logger(__name__)
        
        logger.debug("Debug message test")
        logger.info("Info message test")
        logger.warning("Warning message test")
        logger.error("Error message test")
        
        print("Logging setup test completed successfully!")
        
    except Exception as e:
        print(f"Logging setup failed: {e}")