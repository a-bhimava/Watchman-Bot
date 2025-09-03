"""
Error Handling Utilities with Retry Mechanisms

Comprehensive error handling, retry logic, and recovery mechanisms
for reliable operation of PM Watchman components.
"""

import time
import random
import asyncio
from typing import Callable, Any, Optional, Union, Dict, List, Type
from functools import wraps
from dataclasses import dataclass
from enum import Enum
import logging
from datetime import datetime, timedelta
import traceback
import requests
from requests.exceptions import RequestException, ConnectionError, Timeout


class ErrorSeverity(Enum):
    """Error severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RetryStrategy(Enum):
    """Retry strategy types."""
    FIXED_DELAY = "fixed"
    EXPONENTIAL_BACKOFF = "exponential"
    LINEAR_BACKOFF = "linear"
    RANDOM_JITTER = "jitter"


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    jitter: bool = True
    backoff_multiplier: float = 2.0
    retriable_exceptions: tuple = (RequestException, ConnectionError, Timeout)
    
    def calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay for retry attempt.
        
        Args:
            attempt: Current attempt number (0-based)
            
        Returns:
            Delay in seconds
        """
        if self.strategy == RetryStrategy.FIXED_DELAY:
            delay = self.base_delay
        elif self.strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = self.base_delay * (attempt + 1)
        elif self.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = self.base_delay * (self.backoff_multiplier ** attempt)
        elif self.strategy == RetryStrategy.RANDOM_JITTER:
            delay = random.uniform(0.1, self.base_delay * (attempt + 1))
        else:
            delay = self.base_delay
        
        # Add jitter if enabled
        if self.jitter and self.strategy != RetryStrategy.RANDOM_JITTER:
            jitter_amount = delay * 0.1 * random.uniform(-1, 1)
            delay += jitter_amount
        
        # Respect max delay
        return min(delay, self.max_delay)


@dataclass
class ErrorContext:
    """Context information for error handling."""
    component: str
    operation: str
    attempt: int
    max_attempts: int
    error_type: str
    error_message: str
    timestamp: datetime
    execution_time: Optional[float] = None
    additional_info: Optional[Dict[str, Any]] = None


class CircuitBreakerState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreaker:
    """
    Circuit breaker for preventing cascade failures.
    
    Implements circuit breaker pattern to prevent repeated
    calls to failing services.
    """
    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    success_threshold: int = 3
    
    def __post_init__(self):
        """Initialize circuit breaker state."""
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.logger = logging.getLogger(__name__)
    
    def can_execute(self) -> bool:
        """Check if execution is allowed."""
        if self.state == CircuitBreakerState.CLOSED:
            return True
        
        if self.state == CircuitBreakerState.OPEN:
            if self.last_failure_time and \
               datetime.now() - self.last_failure_time > timedelta(seconds=self.recovery_timeout):
                self.state = CircuitBreakerState.HALF_OPEN
                self.success_count = 0
                self.logger.info("Circuit breaker moving to HALF_OPEN state")
                return True
            return False
        
        if self.state == CircuitBreakerState.HALF_OPEN:
            return True
        
        return False
    
    def record_success(self):
        """Record successful execution."""
        if self.state == CircuitBreakerState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                self.state = CircuitBreakerState.CLOSED
                self.failure_count = 0
                self.logger.info("Circuit breaker recovered, moving to CLOSED state")
        else:
            self.failure_count = 0
    
    def record_failure(self):
        """Record failed execution."""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        if self.state == CircuitBreakerState.CLOSED:
            if self.failure_count >= self.failure_threshold:
                self.state = CircuitBreakerState.OPEN
                self.logger.warning(f"Circuit breaker opened after {self.failure_count} failures")
        elif self.state == CircuitBreakerState.HALF_OPEN:
            self.state = CircuitBreakerState.OPEN
            self.logger.warning("Circuit breaker back to OPEN state after half-open failure")


class PMWatchmanException(Exception):
    """Base exception for PM Watchman errors."""
    def __init__(self, 
                 message: str,
                 component: str = "",
                 operation: str = "",
                 severity: ErrorSeverity = ErrorSeverity.MEDIUM,
                 recoverable: bool = True,
                 context: Optional[Dict[str, Any]] = None):
        """
        Initialize PM Watchman exception.
        
        Args:
            message: Error message
            component: Component where error occurred
            operation: Operation that failed
            severity: Error severity level
            recoverable: Whether error is recoverable
            context: Additional context information
        """
        super().__init__(message)
        self.component = component
        self.operation = operation
        self.severity = severity
        self.recoverable = recoverable
        self.context = context or {}
        self.timestamp = datetime.now()


class ConfigurationError(PMWatchmanException):
    """Configuration-related errors."""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, severity=ErrorSeverity.HIGH, recoverable=False, **kwargs)


class NetworkError(PMWatchmanException):
    """Network-related errors."""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, severity=ErrorSeverity.MEDIUM, recoverable=True, **kwargs)


class DataProcessingError(PMWatchmanException):
    """Data processing errors.""" 
    def __init__(self, message: str, **kwargs):
        super().__init__(message, severity=ErrorSeverity.MEDIUM, recoverable=True, **kwargs)


class StorageError(PMWatchmanException):
    """Storage/file system errors."""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, severity=ErrorSeverity.HIGH, recoverable=True, **kwargs)


class ExternalServiceError(PMWatchmanException):
    """External service integration errors."""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, severity=ErrorSeverity.MEDIUM, recoverable=True, **kwargs)


class ErrorHandler:
    """
    Comprehensive error handling system.
    
    Features:
    - Retry mechanisms with multiple strategies
    - Circuit breaker for external services
    - Error categorization and severity
    - Graceful degradation
    - Error reporting and metrics
    """
    
    def __init__(self):
        """Initialize error handler."""
        self.logger = logging.getLogger(__name__)
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.error_counts: Dict[str, int] = {}
        self.recent_errors: List[ErrorContext] = []
        self.max_recent_errors = 100
    
    def get_circuit_breaker(self, service: str) -> CircuitBreaker:
        """
        Get or create circuit breaker for service.
        
        Args:
            service: Service identifier
            
        Returns:
            CircuitBreaker instance
        """
        if service not in self.circuit_breakers:
            self.circuit_breakers[service] = CircuitBreaker()
        return self.circuit_breakers[service]
    
    def retry_with_backoff(self, 
                          config: Optional[RetryConfig] = None,
                          circuit_breaker_service: Optional[str] = None):
        """
        Decorator for retry with backoff.
        
        Args:
            config: Retry configuration
            circuit_breaker_service: Service name for circuit breaker
            
        Returns:
            Decorator function
        """
        if config is None:
            config = RetryConfig()
        
        def decorator(func):
            @wraps(func)
            def wrapper(*args, **kwargs):
                # Get circuit breaker if specified
                circuit_breaker = None
                if circuit_breaker_service:
                    circuit_breaker = self.get_circuit_breaker(circuit_breaker_service)
                
                last_exception = None
                component = kwargs.get('component', func.__module__)
                operation = kwargs.get('operation', func.__name__)
                
                for attempt in range(config.max_attempts):
                    # Check circuit breaker
                    if circuit_breaker and not circuit_breaker.can_execute():
                        error_msg = f"Circuit breaker open for {circuit_breaker_service}"
                        self.logger.warning(error_msg)
                        raise ExternalServiceError(
                            error_msg,
                            component=component,
                            operation=operation
                        )
                    
                    start_time = datetime.now()
                    
                    try:
                        result = func(*args, **kwargs)
                        
                        # Record success
                        if circuit_breaker:
                            circuit_breaker.record_success()
                        
                        # Log successful retry
                        if attempt > 0:
                            execution_time = (datetime.now() - start_time).total_seconds()
                            self.logger.info(
                                f"{operation} succeeded on attempt {attempt + 1}",
                                extra={
                                    "component": component,
                                    "operation": operation,
                                    "attempt": attempt + 1,
                                    "execution_time": execution_time
                                }
                            )
                        
                        return result
                        
                    except Exception as e:
                        last_exception = e
                        execution_time = (datetime.now() - start_time).total_seconds()
                        
                        # Check if exception is retriable
                        is_retriable = isinstance(e, config.retriable_exceptions)
                        
                        # Record failure in circuit breaker
                        if circuit_breaker:
                            circuit_breaker.record_failure()
                        
                        # Create error context
                        error_context = ErrorContext(
                            component=component,
                            operation=operation,
                            attempt=attempt + 1,
                            max_attempts=config.max_attempts,
                            error_type=type(e).__name__,
                            error_message=str(e),
                            timestamp=datetime.now(),
                            execution_time=execution_time
                        )
                        
                        # Track error
                        self._track_error(error_context)
                        
                        # Log attempt failure
                        if attempt < config.max_attempts - 1 and is_retriable:
                            delay = config.calculate_delay(attempt)
                            self.logger.warning(
                                f"{operation} failed on attempt {attempt + 1}, "
                                f"retrying in {delay:.2f}s: {str(e)}",
                                extra=error_context.__dict__
                            )
                            time.sleep(delay)
                        else:
                            # Final attempt or non-retriable error
                            self.logger.error(
                                f"{operation} failed permanently after {attempt + 1} attempts: {str(e)}",
                                extra=error_context.__dict__,
                                exc_info=True
                            )
                            break
                
                # All retries exhausted
                raise last_exception
            
            return wrapper
        return decorator
    
    def _track_error(self, error_context: ErrorContext):
        """Track error for metrics and analysis."""
        # Update error counts
        error_key = f"{error_context.component}.{error_context.operation}.{error_context.error_type}"
        self.error_counts[error_key] = self.error_counts.get(error_key, 0) + 1
        
        # Store recent errors
        self.recent_errors.append(error_context)
        if len(self.recent_errors) > self.max_recent_errors:
            self.recent_errors.pop(0)
    
    def handle_graceful_degradation(self, 
                                   primary_func: Callable,
                                   fallback_func: Optional[Callable] = None,
                                   fallback_value: Any = None):
        """
        Handle graceful degradation with fallback.
        
        Args:
            primary_func: Primary function to execute
            fallback_func: Fallback function if primary fails
            fallback_value: Static fallback value
            
        Returns:
            Result from primary function or fallback
        """
        def wrapper(*args, **kwargs):
            try:
                return primary_func(*args, **kwargs)
            except Exception as e:
                component = kwargs.get('component', primary_func.__module__)
                operation = kwargs.get('operation', primary_func.__name__)
                
                self.logger.warning(
                    f"Primary function {operation} failed, using fallback: {str(e)}",
                    extra={
                        "component": component,
                        "operation": operation,
                        "error_type": type(e).__name__
                    }
                )
                
                if fallback_func:
                    try:
                        return fallback_func(*args, **kwargs)
                    except Exception as fallback_error:
                        self.logger.error(
                            f"Fallback function also failed: {str(fallback_error)}",
                            extra={
                                "component": component,
                                "operation": f"{operation}_fallback",
                                "error_type": type(fallback_error).__name__
                            }
                        )
                        if fallback_value is not None:
                            return fallback_value
                        raise
                
                if fallback_value is not None:
                    return fallback_value
                
                raise
        
        return wrapper
    
    def get_error_summary(self) -> Dict[str, Any]:
        """
        Get error summary and metrics.
        
        Returns:
            Error summary information
        """
        total_errors = sum(self.error_counts.values())
        recent_error_types = {}
        
        # Analyze recent errors
        for error in self.recent_errors[-20:]:  # Last 20 errors
            key = error.error_type
            recent_error_types[key] = recent_error_types.get(key, 0) + 1
        
        # Circuit breaker status
        circuit_status = {}
        for service, breaker in self.circuit_breakers.items():
            circuit_status[service] = {
                "state": breaker.state.value,
                "failure_count": breaker.failure_count,
                "last_failure": breaker.last_failure_time.isoformat() if breaker.last_failure_time else None
            }
        
        return {
            "total_errors": total_errors,
            "error_types": len(self.error_counts),
            "most_common_errors": sorted(
                self.error_counts.items(),
                key=lambda x: x[1],
                reverse=True
            )[:10],
            "recent_error_types": recent_error_types,
            "circuit_breakers": circuit_status,
            "recent_error_count": len(self.recent_errors)
        }
    
    def health_check(self) -> Dict[str, Any]:
        """
        Get error handler health status.
        
        Returns:
            Health check information
        """
        # Check for concerning error patterns
        high_error_services = []
        for service, breaker in self.circuit_breakers.items():
            if breaker.state != CircuitBreakerState.CLOSED:
                high_error_services.append(service)
        
        recent_critical_errors = len([
            e for e in self.recent_errors[-10:]
            if "critical" in e.error_message.lower()
        ])
        
        return {
            "status": "healthy" if not high_error_services and recent_critical_errors == 0 else "degraded",
            "open_circuit_breakers": high_error_services,
            "recent_critical_errors": recent_critical_errors,
            "total_tracked_errors": len(self.error_counts),
            "active_circuit_breakers": len(self.circuit_breakers)
        }


# Global error handler instance
_error_handler: Optional[ErrorHandler] = None


def get_error_handler() -> ErrorHandler:
    """Get global error handler instance."""
    global _error_handler
    if _error_handler is None:
        _error_handler = ErrorHandler()
    return _error_handler


def retry_on_failure(max_attempts: int = 3,
                    base_delay: float = 1.0,
                    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF,
                    circuit_breaker_service: Optional[str] = None):
    """
    Convenience decorator for retry on failure.
    
    Args:
        max_attempts: Maximum retry attempts
        base_delay: Base delay in seconds
        strategy: Retry strategy
        circuit_breaker_service: Service for circuit breaker
        
    Returns:
        Decorator function
    """
    config = RetryConfig(
        max_attempts=max_attempts,
        base_delay=base_delay,
        strategy=strategy
    )
    
    return get_error_handler().retry_with_backoff(
        config=config,
        circuit_breaker_service=circuit_breaker_service
    )


def graceful_degradation(fallback_func: Optional[Callable] = None,
                        fallback_value: Any = None):
    """
    Convenience decorator for graceful degradation.
    
    Args:
        fallback_func: Fallback function
        fallback_value: Fallback value
        
    Returns:
        Decorator function
    """
    def decorator(func):
        return get_error_handler().handle_graceful_degradation(
            func, 
            fallback_func=fallback_func,
            fallback_value=fallback_value
        )
    
    return decorator