"""
Comprehensive Logging Framework

Robust logging system with structured output, error tracking,
and performance monitoring for PM Watchman.
"""

import logging
import sys
import os
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
import traceback
import json
from functools import wraps
from dataclasses import dataclass, asdict
from enum import Enum


class LogLevel(Enum):
    """Log level enumeration."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class LogContext:
    """Structured logging context information."""
    component: str
    operation: Optional[str] = None
    job_id: Optional[str] = None
    batch_number: Optional[int] = None
    source: Optional[str] = None
    execution_time: Optional[float] = None
    error_type: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary, excluding None values."""
        return {k: v for k, v in asdict(self).items() if v is not None}


class StructuredFormatter(logging.Formatter):
    """Custom formatter for structured logging with JSON output."""
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as structured JSON."""
        # Base log data
        log_data = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # Add context if available
        if hasattr(record, 'context') and record.context:
            log_data.update(record.context.to_dict())
        
        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = {
                "type": record.exc_info[0].__name__ if record.exc_info[0] else None,
                "message": str(record.exc_info[1]) if record.exc_info[1] else None,
                "traceback": traceback.format_exception(*record.exc_info)
            }
        
        # Add extra fields
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'levelname', 'levelno', 'pathname',
                          'filename', 'module', 'exc_info', 'exc_text', 'stack_info',
                          'lineno', 'funcName', 'created', 'msecs', 'relativeCreated',
                          'thread', 'threadName', 'processName', 'process', 'context']:
                log_data[key] = value
        
        return json.dumps(log_data, default=str)


class HumanReadableFormatter(logging.Formatter):
    """Human-readable formatter for console output."""
    
    def __init__(self):
        super().__init__()
        self.format_str = "%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s"
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record for human readability."""
        # Base formatting
        formatter = logging.Formatter(self.format_str)
        formatted = formatter.format(record)
        
        # Add context information if available
        if hasattr(record, 'context') and record.context:
            context_str = " | ".join([
                f"{k}={v}" for k, v in record.context.to_dict().items()
            ])
            formatted += f" | {context_str}"
        
        # Add exception details
        if record.exc_info:
            formatted += f"\n  Exception: {record.exc_info[1]}"
        
        return formatted


class PMWatchmanLogger:
    """
    Comprehensive logging system for PM Watchman.
    
    Features:
    - Structured JSON logging for analysis
    - Human-readable console output
    - Automatic log rotation
    - Performance tracking
    - Error aggregation
    - Context-aware logging
    """
    
    def __init__(self, 
                 log_dir: str = "data/logs",
                 log_level: str = "INFO",
                 enable_console: bool = True,
                 enable_file: bool = True,
                 structured_output: bool = False):
        """
        Initialize logging system.
        
        Args:
            log_dir: Directory for log files
            log_level: Minimum log level
            enable_console: Enable console output
            enable_file: Enable file output
            structured_output: Use JSON structured format
        """
        self.log_dir = Path(log_dir)
        self.log_level = getattr(logging, log_level.upper())
        self.enable_console = enable_console
        self.enable_file = enable_file
        self.structured_output = structured_output
        
        # Performance tracking
        self.performance_metrics = {}
        self.error_counts = {}
        
        # Setup logging
        self._setup_logging()
    
    def _setup_logging(self):
        """Setup logging configuration."""
        # Create log directory
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(self.log_level)
        
        # Remove existing handlers
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # Setup console handler
        if self.enable_console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setLevel(self.log_level)
            
            if self.structured_output:
                console_handler.setFormatter(StructuredFormatter())
            else:
                console_handler.setFormatter(HumanReadableFormatter())
            
            root_logger.addHandler(console_handler)
        
        # Setup file handlers
        if self.enable_file:
            # Main log file
            main_log_file = self.log_dir / "pm_watchman.log"
            main_handler = logging.FileHandler(main_log_file)
            main_handler.setLevel(self.log_level)
            main_handler.setFormatter(StructuredFormatter())
            root_logger.addHandler(main_handler)
            
            # Error log file
            error_log_file = self.log_dir / "errors.log"
            error_handler = logging.FileHandler(error_log_file)
            error_handler.setLevel(logging.ERROR)
            error_handler.setFormatter(StructuredFormatter())
            root_logger.addHandler(error_handler)
            
            # Performance log file
            perf_log_file = self.log_dir / "performance.log"
            perf_handler = logging.FileHandler(perf_log_file)
            perf_handler.setLevel(logging.INFO)
            
            # Only log performance-related entries
            class PerformanceFilter(logging.Filter):
                def filter(self, record):
                    return hasattr(record, 'context') and \
                           record.context and \
                           record.context.execution_time is not None
            
            perf_handler.addFilter(PerformanceFilter())
            perf_handler.setFormatter(StructuredFormatter())
            root_logger.addHandler(perf_handler)
    
    def get_logger(self, name: str) -> logging.Logger:
        """
        Get a logger instance.
        
        Args:
            name: Logger name (usually __name__)
            
        Returns:
            Configured logger instance
        """
        return logging.getLogger(name)
    
    def log_with_context(self, 
                        logger: logging.Logger,
                        level: LogLevel,
                        message: str,
                        context: Optional[LogContext] = None,
                        **kwargs):
        """
        Log message with structured context.
        
        Args:
            logger: Logger instance
            level: Log level
            message: Log message
            context: Structured context information
            **kwargs: Additional fields
        """
        log_record = logger.makeRecord(
            logger.name,
            getattr(logging, level.value),
            "",  # pathname
            0,   # lineno
            message,
            (),  # args
            None,  # exc_info
        )
        
        # Add context
        if context:
            log_record.context = context
        
        # Add extra fields
        for key, value in kwargs.items():
            setattr(log_record, key, value)
        
        logger.handle(log_record)
    
    def track_performance(self, component: str, operation: str):
        """
        Decorator for tracking operation performance.
        
        Args:
            component: Component name
            operation: Operation name
            
        Returns:
            Decorator function
        """
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                start_time = datetime.now()
                logger = self.get_logger(func.__module__)
                
                try:
                    result = func(*args, **kwargs)
                    
                    # Calculate execution time
                    execution_time = (datetime.now() - start_time).total_seconds()
                    
                    # Update performance metrics
                    key = f"{component}.{operation}"
                    if key not in self.performance_metrics:
                        self.performance_metrics[key] = []
                    self.performance_metrics[key].append(execution_time)
                    
                    # Log performance
                    context = LogContext(
                        component=component,
                        operation=operation,
                        execution_time=execution_time
                    )
                    
                    self.log_with_context(
                        logger,
                        LogLevel.INFO,
                        f"{operation} completed successfully",
                        context
                    )
                    
                    return result
                    
                except Exception as e:
                    execution_time = (datetime.now() - start_time).total_seconds()
                    
                    # Track error
                    error_key = f"{component}.{operation}.{type(e).__name__}"
                    self.error_counts[error_key] = self.error_counts.get(error_key, 0) + 1
                    
                    # Log error with context
                    context = LogContext(
                        component=component,
                        operation=operation,
                        execution_time=execution_time,
                        error_type=type(e).__name__
                    )
                    
                    logger.error(
                        f"{operation} failed: {str(e)}",
                        extra={"context": context},
                        exc_info=True
                    )
                    
                    raise
            
            return wrapper
        return decorator
    
    def get_performance_stats(self) -> Dict[str, Dict[str, float]]:
        """
        Get performance statistics.
        
        Returns:
            Dictionary with performance metrics
        """
        stats = {}
        
        for operation, times in self.performance_metrics.items():
            if times:
                stats[operation] = {
                    "count": len(times),
                    "avg_time": sum(times) / len(times),
                    "min_time": min(times),
                    "max_time": max(times),
                    "total_time": sum(times)
                }
        
        return stats
    
    def get_error_summary(self) -> Dict[str, int]:
        """
        Get error count summary.
        
        Returns:
            Dictionary with error counts
        """
        return self.error_counts.copy()
    
    def health_check(self) -> Dict[str, Any]:
        """
        Get logging system health status.
        
        Returns:
            Health check information
        """
        return {
            "log_dir": str(self.log_dir),
            "log_level": logging.getLevelName(self.log_level),
            "handlers_active": len(logging.getLogger().handlers),
            "performance_operations": len(self.performance_metrics),
            "total_errors": sum(self.error_counts.values()),
            "error_types": len(self.error_counts),
            "log_files": [
                {
                    "file": f.name,
                    "size_bytes": f.stat().st_size if f.exists() else 0,
                    "exists": f.exists()
                }
                for f in [
                    self.log_dir / "pm_watchman.log",
                    self.log_dir / "errors.log", 
                    self.log_dir / "performance.log"
                ]
            ]
        }


# Global logger instance
_logger_instance: Optional[PMWatchmanLogger] = None


def initialize_logging(log_dir: str = "data/logs",
                      log_level: str = "INFO",
                      enable_console: bool = True,
                      structured_output: bool = False) -> PMWatchmanLogger:
    """
    Initialize global logging system.
    
    Args:
        log_dir: Directory for log files
        log_level: Minimum log level
        enable_console: Enable console output
        structured_output: Use structured JSON format
        
    Returns:
        PMWatchmanLogger instance
    """
    global _logger_instance
    
    _logger_instance = PMWatchmanLogger(
        log_dir=log_dir,
        log_level=log_level,
        enable_console=enable_console,
        structured_output=structured_output
    )
    
    return _logger_instance


def get_logger(name: str) -> logging.Logger:
    """
    Get logger instance.
    
    Args:
        name: Logger name
        
    Returns:
        Logger instance
    """
    if _logger_instance is None:
        initialize_logging()
    
    return _logger_instance.get_logger(name)


def log_context(component: str,
               operation: Optional[str] = None,
               **kwargs) -> LogContext:
    """
    Create log context.
    
    Args:
        component: Component name
        operation: Operation name
        **kwargs: Additional context fields
        
    Returns:
        LogContext instance
    """
    return LogContext(
        component=component,
        operation=operation,
        **kwargs
    )


def performance_tracker(component: str, operation: str):
    """
    Performance tracking decorator.
    
    Args:
        component: Component name
        operation: Operation name
        
    Returns:
        Decorator function
    """
    if _logger_instance is None:
        initialize_logging()
    
    return _logger_instance.track_performance(component, operation)