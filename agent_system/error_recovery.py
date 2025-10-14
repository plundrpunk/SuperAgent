"""
Error Recovery and Retry Mechanisms for SuperAgent System

Provides robust error handling and automatic recovery for API failures,
timeout issues, and transient errors in the multi-agent workflow.

Features:
- Exponential backoff retry policy
- Circuit breaker pattern for API failures
- Error categorization (transient vs permanent)
- Fallback strategies for each failure type
- Integration with observability system
- Graceful degradation for service outages
"""
import time
import functools
import logging
import subprocess
from typing import Callable, Any, Optional, Dict, List, Type, Union
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import threading

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ErrorCategory(Enum):
    """Error categories for recovery decisions."""
    TRANSIENT = 'transient'  # Retry with backoff
    RATE_LIMIT = 'rate_limit'  # Exponential backoff
    TIMEOUT = 'timeout'  # Retry with increased timeout
    SERVICE_ERROR = 'service_error'  # Circuit breaker
    AUTH_ERROR = 'auth_error'  # No retry, alert
    INVALID_INPUT = 'invalid_input'  # No retry, return error
    NETWORK_ERROR = 'network_error'  # Retry with backoff
    SUBPROCESS_TIMEOUT = 'subprocess_timeout'  # Kill process, retry once
    RESOURCE_EXHAUSTED = 'resource_exhausted'  # Circuit breaker
    PERMANENT = 'permanent'  # No retry


class ErrorClassifier:
    """
    Classifies errors into categories for recovery decisions.

    Uses error message patterns and exception types to determine
    the appropriate recovery strategy.
    """

    # HTTP status code mappings
    STATUS_CODE_MAPPING = {
        429: ErrorCategory.RATE_LIMIT,
        401: ErrorCategory.AUTH_ERROR,
        403: ErrorCategory.AUTH_ERROR,
        400: ErrorCategory.INVALID_INPUT,
        422: ErrorCategory.INVALID_INPUT,
        500: ErrorCategory.SERVICE_ERROR,
        502: ErrorCategory.SERVICE_ERROR,
        503: ErrorCategory.SERVICE_ERROR,
        504: ErrorCategory.TIMEOUT,
    }

    # Exception type mappings
    EXCEPTION_MAPPING = {
        'TimeoutError': ErrorCategory.TIMEOUT,
        'ConnectionError': ErrorCategory.NETWORK_ERROR,
        'ConnectionRefusedError': ErrorCategory.NETWORK_ERROR,
        'ConnectionResetError': ErrorCategory.NETWORK_ERROR,
        'BrokenPipeError': ErrorCategory.NETWORK_ERROR,
        'OSError': ErrorCategory.TRANSIENT,
    }

    # Error message patterns
    MESSAGE_PATTERNS = {
        'rate limit': ErrorCategory.RATE_LIMIT,
        'too many requests': ErrorCategory.RATE_LIMIT,
        'quota exceeded': ErrorCategory.RATE_LIMIT,
        'timeout': ErrorCategory.TIMEOUT,
        'timed out': ErrorCategory.TIMEOUT,
        'connection': ErrorCategory.NETWORK_ERROR,
        'network': ErrorCategory.NETWORK_ERROR,
        'authentication': ErrorCategory.AUTH_ERROR,
        'unauthorized': ErrorCategory.AUTH_ERROR,
        'invalid': ErrorCategory.INVALID_INPUT,
        'bad request': ErrorCategory.INVALID_INPUT,
        'not found': ErrorCategory.PERMANENT,
        'resource exhausted': ErrorCategory.RESOURCE_EXHAUSTED,
    }

    @classmethod
    def classify_error(
        cls,
        error: Exception,
        status_code: Optional[int] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> ErrorCategory:
        """
        Classify an error into a recovery category.

        Args:
            error: The exception that occurred
            status_code: Optional HTTP status code
            context: Optional context dict with additional info

        Returns:
            ErrorCategory for the error
        """
        # Check subprocess timeout from context FIRST (most specific)
        if context and context.get('is_subprocess_timeout'):
            return ErrorCategory.SUBPROCESS_TIMEOUT

        # Check status code (most definitive for HTTP errors)
        if status_code and status_code in cls.STATUS_CODE_MAPPING:
            return cls.STATUS_CODE_MAPPING[status_code]

        # Check exception type
        error_type = type(error).__name__
        if error_type in cls.EXCEPTION_MAPPING:
            return cls.EXCEPTION_MAPPING[error_type]

        # Check error message patterns
        error_msg = str(error).lower()
        for pattern, category in cls.MESSAGE_PATTERNS.items():
            if pattern in error_msg:
                return category

        # Default to transient (safe default - will retry)
        return ErrorCategory.TRANSIENT


@dataclass
class RetryPolicy:
    """
    Retry policy with exponential backoff.

    Configuration:
    - max_attempts: Maximum number of retry attempts
    - base_delay: Initial delay in seconds
    - max_delay: Maximum delay in seconds
    - backoff_factor: Multiplier for exponential backoff
    - jitter: Add randomness to delay (reduces thundering herd)
    """
    max_attempts: int = 3
    base_delay: float = 1.0
    max_delay: float = 60.0
    backoff_factor: float = 2.0
    jitter: bool = True

    def calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay for given attempt number.

        Args:
            attempt: Attempt number (1-indexed)

        Returns:
            Delay in seconds
        """
        import random

        # Exponential backoff: base_delay * (backoff_factor ^ (attempt - 1))
        delay = min(
            self.base_delay * (self.backoff_factor ** (attempt - 1)),
            self.max_delay
        )

        # Add jitter (randomize +/- 25%)
        if self.jitter:
            jitter_range = delay * 0.25
            delay += random.uniform(-jitter_range, jitter_range)

        return max(0, delay)

    def should_retry(self, attempt: int, error_category: ErrorCategory) -> bool:
        """
        Determine if error should be retried.

        Args:
            attempt: Current attempt number
            error_category: Category of error

        Returns:
            True if should retry
        """
        # Never retry certain error categories
        if error_category in [
            ErrorCategory.AUTH_ERROR,
            ErrorCategory.INVALID_INPUT,
            ErrorCategory.PERMANENT
        ]:
            return False

        # Check max attempts
        if attempt >= self.max_attempts:
            return False

        return True


@dataclass
class CircuitBreakerConfig:
    """
    Circuit breaker configuration.

    States:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Failure threshold exceeded, requests fail fast
    - HALF_OPEN: Testing if service recovered
    """
    failure_threshold: int = 5
    success_threshold: int = 2
    timeout_seconds: float = 60.0
    half_open_max_calls: int = 3


class CircuitBreakerState(Enum):
    """Circuit breaker states."""
    CLOSED = 'closed'
    OPEN = 'open'
    HALF_OPEN = 'half_open'


class CircuitBreaker:
    """
    Circuit breaker pattern implementation.

    Prevents cascading failures by failing fast when a service
    is experiencing errors.
    """

    def __init__(self, name: str, config: Optional[CircuitBreakerConfig] = None):
        """
        Initialize circuit breaker.

        Args:
            name: Name of the circuit breaker (e.g., 'anthropic_api')
            config: Optional configuration
        """
        self.name = name
        self.config = config or CircuitBreakerConfig()

        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[datetime] = None
        self._half_open_calls = 0
        self._lock = threading.Lock()

        logger.info(f"Circuit breaker '{name}' initialized: {self.config}")

    @property
    def state(self) -> CircuitBreakerState:
        """Get current state."""
        return self._state

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection.

        Args:
            func: Function to execute
            *args, **kwargs: Arguments for function

        Returns:
            Function result

        Raises:
            CircuitBreakerOpenError: If circuit is open
            Original exception if function fails
        """
        with self._lock:
            # Check if circuit should transition from OPEN to HALF_OPEN
            if self._state == CircuitBreakerState.OPEN:
                if self._should_attempt_reset():
                    self._transition_to_half_open()
                else:
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker '{self.name}' is OPEN. "
                        f"Retry after {self.config.timeout_seconds}s"
                    )

            # Limit calls in HALF_OPEN state
            if self._state == CircuitBreakerState.HALF_OPEN:
                if self._half_open_calls >= self.config.half_open_max_calls:
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker '{self.name}' is HALF_OPEN. "
                        "Max test calls reached"
                    )
                self._half_open_calls += 1

        # Execute function
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self._last_failure_time is None:
            return False

        elapsed = (datetime.now() - self._last_failure_time).total_seconds()
        return elapsed >= self.config.timeout_seconds

    def _transition_to_half_open(self):
        """Transition from OPEN to HALF_OPEN."""
        logger.info(f"Circuit breaker '{self.name}': OPEN -> HALF_OPEN")
        self._state = CircuitBreakerState.HALF_OPEN
        self._half_open_calls = 0

        # Emit event
        self._emit_event('circuit_breaker_half_open')

    def _on_success(self):
        """Handle successful call."""
        with self._lock:
            if self._state == CircuitBreakerState.HALF_OPEN:
                self._success_count += 1
                logger.info(
                    f"Circuit breaker '{self.name}': Success {self._success_count}/"
                    f"{self.config.success_threshold} in HALF_OPEN"
                )

                if self._success_count >= self.config.success_threshold:
                    self._transition_to_closed()
            elif self._state == CircuitBreakerState.CLOSED:
                # Reset failure count on success
                if self._failure_count > 0:
                    logger.info(f"Circuit breaker '{self.name}': Resetting failure count")
                    self._failure_count = 0

    def _on_failure(self):
        """Handle failed call."""
        with self._lock:
            self._last_failure_time = datetime.now()

            if self._state == CircuitBreakerState.HALF_OPEN:
                # Failure in HALF_OPEN -> back to OPEN
                logger.warning(f"Circuit breaker '{self.name}': Failure in HALF_OPEN -> OPEN")
                self._transition_to_open()
            elif self._state == CircuitBreakerState.CLOSED:
                self._failure_count += 1
                logger.warning(
                    f"Circuit breaker '{self.name}': Failure {self._failure_count}/"
                    f"{self.config.failure_threshold}"
                )

                if self._failure_count >= self.config.failure_threshold:
                    self._transition_to_open()

    def _transition_to_open(self):
        """Transition to OPEN state."""
        logger.error(f"Circuit breaker '{self.name}': -> OPEN")
        self._state = CircuitBreakerState.OPEN
        self._success_count = 0
        self._half_open_calls = 0

        # Emit event
        self._emit_event('circuit_breaker_opened')

    def _transition_to_closed(self):
        """Transition to CLOSED state."""
        logger.info(f"Circuit breaker '{self.name}': -> CLOSED")
        self._state = CircuitBreakerState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._half_open_calls = 0

        # Emit event
        self._emit_event('circuit_breaker_closed')

    def _emit_event(self, event_type: str):
        """Emit observability event."""
        try:
            from agent_system.observability.event_stream import emit_event
            emit_event(event_type, {
                'circuit_breaker': self.name,
                'state': self._state.value,
                'failure_count': self._failure_count,
                'success_count': self._success_count,
                'timestamp': time.time()
            })
        except Exception as e:
            logger.warning(f"Failed to emit circuit breaker event: {e}")

    def reset(self):
        """Manually reset circuit breaker to CLOSED state."""
        with self._lock:
            logger.info(f"Circuit breaker '{self.name}': Manual reset")
            self._transition_to_closed()

    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics."""
        return {
            'name': self.name,
            'state': self._state.value,
            'failure_count': self._failure_count,
            'success_count': self._success_count,
            'last_failure_time': self._last_failure_time.isoformat() if self._last_failure_time else None
        }


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open."""
    pass


# Global circuit breakers registry
_circuit_breakers: Dict[str, CircuitBreaker] = {}
_cb_lock = threading.Lock()


def get_circuit_breaker(name: str, config: Optional[CircuitBreakerConfig] = None) -> CircuitBreaker:
    """
    Get or create a circuit breaker by name.

    Args:
        name: Circuit breaker name
        config: Optional configuration (only used on first creation)

    Returns:
        CircuitBreaker instance
    """
    if name not in _circuit_breakers:
        with _cb_lock:
            if name not in _circuit_breakers:
                _circuit_breakers[name] = CircuitBreaker(name, config)

    return _circuit_breakers[name]


@dataclass
class FallbackStrategy:
    """
    Fallback strategy for when primary action fails.

    Strategies:
    - RETURN_DEFAULT: Return a default value
    - SKIP_VALIDATION: Skip optional validation step
    - USE_CACHE: Use cached result
    - SIMPLER_MODEL: Use simpler/cheaper model
    - ESCALATE_TO_HITL: Escalate to human in the loop
    """
    strategy_type: str
    default_value: Any = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class FallbackType(Enum):
    """Fallback strategy types."""
    RETURN_DEFAULT = 'return_default'
    SKIP_VALIDATION = 'skip_validation'
    USE_CACHE = 'use_cache'
    SIMPLER_MODEL = 'simpler_model'
    ESCALATE_TO_HITL = 'escalate_to_hitl'
    IN_MEMORY_CACHE = 'in_memory_cache'
    MARK_UNVALIDATED = 'mark_unvalidated'


def retry_with_backoff(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    backoff_factor: float = 2.0,
    retryable_errors: Optional[List[ErrorCategory]] = None,
    fallback: Optional[FallbackStrategy] = None,
    circuit_breaker_name: Optional[str] = None,
    emit_events: bool = True
):
    """
    Decorator for retry with exponential backoff.

    Args:
        max_attempts: Maximum retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        backoff_factor: Exponential backoff multiplier
        retryable_errors: List of error categories to retry (None = all transient)
        fallback: Optional fallback strategy if all retries fail
        circuit_breaker_name: Optional circuit breaker to use
        emit_events: Emit observability events

    Example:
        @retry_with_backoff(max_attempts=3, base_delay=2.0)
        def call_anthropic_api():
            # API call here
            pass
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            policy = RetryPolicy(
                max_attempts=max_attempts,
                base_delay=base_delay,
                max_delay=max_delay,
                backoff_factor=backoff_factor
            )

            # Get circuit breaker if specified
            cb = get_circuit_breaker(circuit_breaker_name) if circuit_breaker_name else None

            last_error = None

            for attempt in range(1, max_attempts + 1):
                try:
                    # Emit retry event (if not first attempt)
                    if attempt > 1 and emit_events:
                        _emit_retry_event(func.__name__, attempt, max_attempts)

                    # Execute with circuit breaker if available
                    if cb:
                        result = cb.call(func, *args, **kwargs)
                    else:
                        result = func(*args, **kwargs)

                    # Success
                    return result

                except CircuitBreakerOpenError:
                    # Circuit breaker open - fail fast, don't retry
                    logger.error(f"{func.__name__}: Circuit breaker open, failing fast")
                    raise

                except Exception as e:
                    last_error = e

                    # Classify error
                    error_category = ErrorClassifier.classify_error(e)

                    # Emit error event
                    if emit_events:
                        _emit_error_event(func.__name__, e, error_category, attempt)

                    # Check if should retry
                    if not policy.should_retry(attempt, error_category):
                        logger.error(
                            f"{func.__name__}: Error category {error_category.value} "
                            f"not retryable or max attempts reached"
                        )
                        break

                    # Calculate delay
                    if attempt < max_attempts:
                        delay = policy.calculate_delay(attempt)
                        logger.warning(
                            f"{func.__name__}: Attempt {attempt}/{max_attempts} failed "
                            f"({error_category.value}). Retrying in {delay:.2f}s..."
                        )
                        time.sleep(delay)
                    else:
                        logger.error(
                            f"{func.__name__}: All {max_attempts} attempts failed"
                        )

            # All retries failed - try fallback
            if fallback:
                logger.info(f"{func.__name__}: Applying fallback strategy: {fallback.strategy_type}")
                return _apply_fallback(fallback, last_error)

            # No fallback - raise last error
            raise last_error

        return wrapper
    return decorator


def _emit_retry_event(func_name: str, attempt: int, max_attempts: int):
    """Emit retry event to observability system."""
    try:
        from agent_system.observability.event_stream import emit_event
        emit_event('retry_attempted', {
            'function': func_name,
            'attempt': attempt,
            'max_attempts': max_attempts,
            'timestamp': time.time()
        })
    except Exception as e:
        logger.warning(f"Failed to emit retry event: {e}")


def _emit_error_event(func_name: str, error: Exception, category: ErrorCategory, attempt: int):
    """Emit error event to observability system."""
    try:
        from agent_system.observability.event_stream import emit_event
        emit_event('error_occurred', {
            'function': func_name,
            'error_type': type(error).__name__,
            'error_message': str(error),
            'error_category': category.value,
            'attempt': attempt,
            'timestamp': time.time()
        })
    except Exception as e:
        logger.warning(f"Failed to emit error event: {e}")


def _apply_fallback(strategy: FallbackStrategy, error: Exception) -> Any:
    """
    Apply fallback strategy.

    Args:
        strategy: Fallback strategy to apply
        error: The error that triggered fallback

    Returns:
        Fallback result
    """
    if strategy.strategy_type == FallbackType.RETURN_DEFAULT.value:
        logger.info(f"Fallback: Returning default value")
        return strategy.default_value

    elif strategy.strategy_type == FallbackType.SKIP_VALIDATION.value:
        logger.warning(f"Fallback: Skipping validation (marked as unvalidated)")
        return {
            'success': True,
            'validated': False,
            'fallback_applied': True,
            'error': str(error)
        }

    elif strategy.strategy_type == FallbackType.MARK_UNVALIDATED.value:
        logger.warning(f"Fallback: Marking as unvalidated")
        return {
            'validated': False,
            'fallback_reason': str(error),
            'fallback_applied': True
        }

    elif strategy.strategy_type == FallbackType.ESCALATE_TO_HITL.value:
        logger.warning(f"Fallback: Escalating to HITL")
        try:
            from agent_system.hitl.queue import HITLQueue
            hitl_queue = HITLQueue()
            task_data = {
                'error': str(error),
                'function': strategy.metadata.get('function', 'unknown'),
                'reason': 'All retries failed'
            }
            hitl_queue.enqueue(task_data)
            return {
                'success': False,
                'escalated_to_hitl': True,
                'error': str(error)
            }
        except Exception as hitl_error:
            logger.error(f"Fallback escalation failed: {hitl_error}")
            raise error

    else:
        logger.error(f"Unknown fallback strategy: {strategy.strategy_type}")
        raise error


def with_timeout(timeout_seconds: float, kill_on_timeout: bool = True):
    """
    Decorator for subprocess execution with timeout.

    Args:
        timeout_seconds: Timeout in seconds
        kill_on_timeout: Kill subprocess on timeout

    Example:
        @with_timeout(timeout_seconds=30)
        def run_tests():
            subprocess.run(['pytest', 'tests/'])
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            import signal
            import threading

            result = [None]
            exception = [None]

            def target():
                try:
                    result[0] = func(*args, **kwargs)
                except Exception as e:
                    exception[0] = e

            thread = threading.Thread(target=target)
            thread.daemon = True
            thread.start()
            thread.join(timeout_seconds)

            if thread.is_alive():
                # Timeout occurred
                logger.error(f"{func.__name__}: Timeout after {timeout_seconds}s")

                if kill_on_timeout:
                    # This is simplified - in production would need proper process tracking
                    logger.warning(f"{func.__name__}: Killing subprocess")

                raise TimeoutError(
                    f"{func.__name__} timed out after {timeout_seconds}s"
                )

            if exception[0]:
                raise exception[0]

            return result[0]

        return wrapper
    return decorator


# Agent-specific recovery configurations
AGENT_RECOVERY_CONFIGS = {
    'scribe': {
        'retry_policy': RetryPolicy(max_attempts=3, base_delay=2.0),
        'fallback': FallbackStrategy(
            strategy_type=FallbackType.SIMPLER_MODEL.value,
            metadata={'fallback_model': 'claude-haiku'}
        ),
        'circuit_breaker': 'anthropic_api'
    },
    'runner': {
        'retry_policy': RetryPolicy(max_attempts=2, base_delay=5.0),
        'fallback': FallbackStrategy(
            strategy_type=FallbackType.RETURN_DEFAULT.value,
            default_value={'success': False, 'error': 'Test execution failed'}
        ),
        'circuit_breaker': None  # No circuit breaker for subprocess execution
    },
    'medic': {
        'retry_policy': RetryPolicy(max_attempts=2, base_delay=2.0),
        'fallback': FallbackStrategy(
            strategy_type=FallbackType.ESCALATE_TO_HITL.value,
            metadata={'reason': 'Fix failed after retries'}
        ),
        'circuit_breaker': 'anthropic_api'
    },
    'critic': {
        'retry_policy': RetryPolicy(max_attempts=1, base_delay=0.0),
        'fallback': None,  # Fail fast
        'circuit_breaker': None
    },
    'gemini': {
        'retry_policy': RetryPolicy(max_attempts=2, base_delay=3.0),
        'fallback': FallbackStrategy(
            strategy_type=FallbackType.MARK_UNVALIDATED.value
        ),
        'circuit_breaker': 'gemini_api'
    }
}


def get_agent_recovery_decorator(agent_name: str):
    """
    Get configured retry decorator for specific agent.

    Args:
        agent_name: Name of agent (scribe, runner, medic, critic, gemini)

    Returns:
        Configured retry_with_backoff decorator

    Example:
        @get_agent_recovery_decorator('scribe')
        def execute(self, **kwargs):
            # Agent execution logic
            pass
    """
    config = AGENT_RECOVERY_CONFIGS.get(agent_name, {})
    policy = config.get('retry_policy', RetryPolicy())
    fallback = config.get('fallback')
    circuit_breaker_name = config.get('circuit_breaker')

    return retry_with_backoff(
        max_attempts=policy.max_attempts,
        base_delay=policy.base_delay,
        max_delay=policy.max_delay,
        backoff_factor=policy.backoff_factor,
        fallback=fallback,
        circuit_breaker_name=circuit_breaker_name
    )


# Graceful degradation utilities

class GracefulDegradation:
    """
    Utilities for graceful degradation when services are unavailable.
    """

    _in_memory_cache: Dict[str, Any] = {}
    _cache_lock = threading.Lock()

    @staticmethod
    def redis_with_fallback(redis_client, operation: str, *args, **kwargs) -> Any:
        """
        Execute Redis operation with in-memory cache fallback.

        Args:
            redis_client: RedisClient instance
            operation: Operation name (e.g., 'get', 'set')
            *args, **kwargs: Operation arguments

        Returns:
            Operation result or fallback result
        """
        try:
            # Try Redis operation
            method = getattr(redis_client, operation)
            return method(*args, **kwargs)

        except Exception as e:
            logger.warning(f"Redis operation '{operation}' failed: {e}. Using in-memory cache.")

            # Fallback to in-memory cache
            if operation == 'get':
                key = args[0]
                return GracefulDegradation._in_memory_cache.get(key)

            elif operation == 'set':
                key = args[0]
                value = args[1]
                with GracefulDegradation._cache_lock:
                    GracefulDegradation._in_memory_cache[key] = value
                return True

            elif operation == 'delete':
                key = args[0]
                with GracefulDegradation._cache_lock:
                    return GracefulDegradation._in_memory_cache.pop(key, None) is not None

            else:
                logger.error(f"No fallback for Redis operation: {operation}")
                raise

    @staticmethod
    def vector_db_with_fallback(vector_client, query: str, **kwargs) -> List[Dict[str, Any]]:
        """
        Query vector DB with empty result fallback.

        Args:
            vector_client: VectorClient instance
            query: Search query
            **kwargs: Additional arguments

        Returns:
            Search results or empty list
        """
        try:
            return vector_client.search_test_patterns(query, **kwargs)
        except Exception as e:
            logger.warning(f"Vector DB query failed: {e}. Proceeding without RAG enhancement.")
            return []

    @staticmethod
    def gemini_with_fallback(gemini_validator, test_path: str, **kwargs) -> Dict[str, Any]:
        """
        Execute Gemini validation with unvalidated fallback.

        Args:
            gemini_validator: GeminiAgent instance
            test_path: Path to test file
            **kwargs: Additional arguments

        Returns:
            Validation result or unvalidated marker
        """
        try:
            return gemini_validator.execute(test_path=test_path, **kwargs)
        except Exception as e:
            logger.warning(
                f"Gemini validation failed: {e}. "
                "Marking test as unvalidated."
            )
            return {
                'success': True,
                'validated': False,
                'error': str(e),
                'fallback_applied': True,
                'message': 'Test created but not validated (Gemini unavailable)'
            }


# Example usage and testing
if __name__ == '__main__':
    # Example 1: Retry with exponential backoff
    @retry_with_backoff(max_attempts=3, base_delay=1.0)
    def flaky_api_call():
        import random
        if random.random() < 0.7:
            raise ConnectionError("Network error")
        return "Success!"

    # Example 2: Circuit breaker
    cb = get_circuit_breaker('test_service')

    def call_service():
        import random
        if random.random() < 0.8:
            raise Exception("Service error")
        return "OK"

    # Example 3: Graceful degradation
    from agent_system.state.redis_client import RedisClient

    redis_client = RedisClient()

    # This will use Redis if available, in-memory cache if not
    result = GracefulDegradation.redis_with_fallback(
        redis_client,
        'set',
        'test_key',
        {'data': 'value'}
    )

    print("Error recovery module loaded successfully")
