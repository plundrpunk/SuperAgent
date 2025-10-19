# Error Recovery Integration Guide

This guide shows how to integrate the error recovery and retry mechanisms into SuperAgent agents and services.

## Overview

The error recovery system provides:
- **Retry with exponential backoff** for transient failures
- **Circuit breaker pattern** to prevent cascading failures
- **Error categorization** for intelligent retry decisions
- **Fallback strategies** for graceful degradation
- **Observability integration** for monitoring and alerting

## Quick Start

### 1. Basic Retry Decorator

```python
from agent_system.error_recovery import retry_with_backoff

@retry_with_backoff(max_attempts=3, base_delay=2.0)
def call_anthropic_api():
    # Your API call here
    pass
```

### 2. Agent-Specific Recovery

Use pre-configured retry policies for each agent type:

```python
from agent_system.error_recovery import get_agent_recovery_decorator

class ScribeAgent(BaseAgent):
    @get_agent_recovery_decorator('scribe')
    def execute(self, **kwargs):
        # Scribe execution logic
        # Automatically retries with:
        # - max_attempts=3
        # - base_delay=2.0
        # - Fallback to simpler model on failure
        # - Circuit breaker on API failures
        pass
```

### 3. Graceful Degradation

Handle service outages gracefully:

```python
from agent_system.error_recovery import GracefulDegradation

# Redis with in-memory fallback
result = GracefulDegradation.redis_with_fallback(
    redis_client, 'get', 'session_key'
)

# Vector DB with empty result fallback
patterns = GracefulDegradation.vector_db_with_fallback(
    vector_client, 'test query'
)

# Gemini with unvalidated marker fallback
validation = GracefulDegradation.gemini_with_fallback(
    gemini_agent, 'test.spec.ts'
)
```

## Agent-Specific Configurations

### Scribe (Test Writer)
- **Retry Policy**: 3 attempts, 2s base delay
- **Fallback**: Switch to simpler model (Haiku) on failure
- **Circuit Breaker**: `anthropic_api`
- **Use Case**: Writing tests, generating code

```python
@get_agent_recovery_decorator('scribe')
def execute(self, task_description: str, **kwargs):
    # If Sonnet fails, automatically retries with Haiku
    pass
```

### Runner (Test Executor)
- **Retry Policy**: 2 attempts, 5s base delay
- **Fallback**: Return error result
- **Circuit Breaker**: None (subprocess execution)
- **Use Case**: Running Playwright tests

```python
@get_agent_recovery_decorator('runner')
def execute(self, test_path: str, **kwargs):
    # Retries test execution on transient failures
    pass
```

### Medic (Bug Fixer)
- **Retry Policy**: 2 attempts, 2s base delay
- **Fallback**: Escalate to HITL queue
- **Circuit Breaker**: `anthropic_api`
- **Use Case**: Fixing test failures

```python
@get_agent_recovery_decorator('medic')
def execute(self, test_path: str, error_log: str, **kwargs):
    # Attempts fix, escalates to HITL on repeated failure
    pass
```

### Critic (Pre-Validator)
- **Retry Policy**: No retries (fail fast)
- **Fallback**: None
- **Circuit Breaker**: None
- **Use Case**: Static analysis, pre-validation

```python
@get_agent_recovery_decorator('critic')
def execute(self, test_content: str, **kwargs):
    # Fails fast - no retries needed for static analysis
    pass
```

### Gemini (Browser Validator)
- **Retry Policy**: 2 attempts, 3s base delay
- **Fallback**: Mark as unvalidated
- **Circuit Breaker**: `gemini_api`
- **Use Case**: Browser-based validation

```python
@get_agent_recovery_decorator('gemini')
def execute(self, test_path: str, **kwargs):
    # Retries on network errors, marks unvalidated on failure
    pass
```

## Error Categories

The system automatically categorizes errors for intelligent retry decisions:

### Retryable Errors
- `TRANSIENT`: Temporary failures → Retry with backoff
- `RATE_LIMIT`: API rate limiting → Exponential backoff
- `TIMEOUT`: Request timeout → Retry with increased timeout
- `NETWORK_ERROR`: Connection issues → Retry with backoff
- `SERVICE_ERROR`: Server errors (500) → Circuit breaker

### Non-Retryable Errors
- `AUTH_ERROR`: Authentication failures (401, 403) → No retry, alert
- `INVALID_INPUT`: Bad request (400) → No retry, return error
- `PERMANENT`: Resource not found → No retry

## Circuit Breaker Pattern

Circuit breakers prevent cascading failures by failing fast when a service is experiencing errors.

### States
- **CLOSED**: Normal operation, requests pass through
- **OPEN**: Failure threshold exceeded, requests fail fast
- **HALF_OPEN**: Testing if service recovered

### Usage

```python
from agent_system.error_recovery import get_circuit_breaker

# Get circuit breaker for a service
cb = get_circuit_breaker('anthropic_api')

# Execute with protection
try:
    result = cb.call(lambda: api_call())
except CircuitBreakerOpenError:
    # Service is down, fail fast
    logger.error("API circuit breaker is open")
```

### Configuration

```python
from agent_system.error_recovery import CircuitBreakerConfig

config = CircuitBreakerConfig(
    failure_threshold=5,      # Open after 5 failures
    success_threshold=2,      # Close after 2 successes in HALF_OPEN
    timeout_seconds=60.0,     # Wait 60s before trying HALF_OPEN
    half_open_max_calls=3     # Max test calls in HALF_OPEN
)

cb = get_circuit_breaker('my_service', config)
```

## Fallback Strategies

### Return Default Value

```python
from agent_system.error_recovery import FallbackStrategy, FallbackType

fallback = FallbackStrategy(
    strategy_type=FallbackType.RETURN_DEFAULT.value,
    default_value={'status': 'unavailable'}
)

@retry_with_backoff(max_attempts=3, fallback=fallback)
def get_data():
    # If all retries fail, returns default value
    pass
```

### Skip Optional Validation

```python
fallback = FallbackStrategy(
    strategy_type=FallbackType.SKIP_VALIDATION.value
)

@retry_with_backoff(max_attempts=2, fallback=fallback)
def validate_test():
    # If validation fails, marks as unvalidated and continues
    pass
```

### Escalate to HITL

```python
fallback = FallbackStrategy(
    strategy_type=FallbackType.ESCALATE_TO_HITL.value,
    metadata={'reason': 'Fix failed after retries'}
)

@retry_with_backoff(max_attempts=3, fallback=fallback)
def fix_test():
    # If fix fails, escalates to human in the loop
    pass
```

## Observability Integration

The error recovery system emits events to the observability system:

### Events Emitted

1. **error_occurred**: When an error is caught
   ```json
   {
     "event_type": "error_occurred",
     "function": "call_anthropic_api",
     "error_type": "ConnectionError",
     "error_message": "Network timeout",
     "error_category": "network_error",
     "attempt": 1
   }
   ```

2. **retry_attempted**: When a retry is triggered
   ```json
   {
     "event_type": "retry_attempted",
     "function": "call_anthropic_api",
     "attempt": 2,
     "max_attempts": 3
   }
   ```

3. **circuit_breaker_opened**: When circuit opens
   ```json
   {
     "event_type": "circuit_breaker_opened",
     "circuit_breaker": "anthropic_api",
     "failure_count": 5
   }
   ```

4. **circuit_breaker_closed**: When circuit closes
   ```json
   {
     "event_type": "circuit_breaker_closed",
     "circuit_breaker": "anthropic_api"
   }
   ```

### Monitoring

```python
from agent_system.error_recovery import get_circuit_breaker

# Get circuit breaker stats
cb = get_circuit_breaker('anthropic_api')
stats = cb.get_stats()

print(f"State: {stats['state']}")
print(f"Failures: {stats['failure_count']}")
```

## Integration Examples

### Example 1: Scribe Agent with RAG Fallback

```python
from agent_system.agents.base_agent import BaseAgent, AgentResult
from agent_system.error_recovery import (
    get_agent_recovery_decorator,
    GracefulDegradation
)

class ScribeAgent(BaseAgent):
    def __init__(self):
        super().__init__('scribe')
        self.vector_client = VectorClient()

    @get_agent_recovery_decorator('scribe')
    def execute(self, task_description: str, **kwargs):
        # Query vector DB with fallback (graceful degradation)
        similar_patterns = GracefulDegradation.vector_db_with_fallback(
            self.vector_client,
            task_description
        )

        # If vector DB is down, similar_patterns will be []
        # Scribe continues without RAG enhancement

        # Generate test with retry logic built in
        test_code = self._generate_test(task_description, similar_patterns)

        return AgentResult(
            success=True,
            data={'test_code': test_code},
            metadata={'rag_patterns': len(similar_patterns)}
        )
```

### Example 2: Runner with Extended Timeout

```python
from agent_system.error_recovery import retry_with_backoff
import subprocess

class RunnerAgent(BaseAgent):
    @retry_with_backoff(
        max_attempts=2,
        base_delay=5.0,
        fallback=FallbackStrategy(
            strategy_type=FallbackType.RETURN_DEFAULT.value,
            default_value={'success': False, 'error': 'Test execution failed'}
        )
    )
    def execute(self, test_path: str, **kwargs):
        # Run Playwright test with timeout
        result = subprocess.run(
            ['npx', 'playwright', 'test', test_path],
            capture_output=True,
            timeout=60,  # 60 second timeout
            text=True
        )

        if result.returncode != 0:
            raise Exception(f"Test failed: {result.stderr}")

        return AgentResult(
            success=True,
            data={'output': result.stdout}
        )
```

### Example 3: State Management with Redis Fallback

```python
from agent_system.state.redis_client import RedisClient
from agent_system.error_recovery import GracefulDegradation

class StateManager:
    def __init__(self):
        self.redis = RedisClient()

    def get_session(self, session_id: str):
        # Redis with in-memory fallback
        return GracefulDegradation.redis_with_fallback(
            self.redis, 'get', f'session:{session_id}'
        )

    def set_session(self, session_id: str, data: dict):
        # Redis with in-memory fallback
        return GracefulDegradation.redis_with_fallback(
            self.redis, 'set', f'session:{session_id}', data
        )
```

## Best Practices

### 1. Choose Appropriate Retry Counts
- **Fast operations** (< 1s): max_attempts=3
- **Slow operations** (> 5s): max_attempts=2
- **Expensive operations**: max_attempts=2 with fallback

### 2. Set Realistic Timeouts
- **API calls**: 30-60 seconds
- **Test execution**: 60-120 seconds
- **Browser operations**: 45-90 seconds

### 3. Use Circuit Breakers for External Services
- Anthropic API
- Google Gemini API
- OpenAI API
- External databases

### 4. Implement Fallbacks for Optional Features
- RAG enhancement → Continue without patterns
- Browser validation → Mark as unvalidated
- Voice transcription → Use text input

### 5. Monitor Circuit Breaker States
- Alert when circuit opens
- Track error rates by category
- Review fallback usage patterns

## Testing

### Unit Test Example

```python
from agent_system.error_recovery import retry_with_backoff

def test_retry_with_backoff():
    call_count = [0]

    @retry_with_backoff(max_attempts=3, base_delay=0.01, emit_events=False)
    def flaky_function():
        call_count[0] += 1
        if call_count[0] < 3:
            raise ConnectionError("Network error")
        return "success"

    result = flaky_function()

    assert result == "success"
    assert call_count[0] == 3
```

### Integration Test Example

```python
from agent_system.error_recovery import get_circuit_breaker

def test_circuit_breaker_integration():
    cb = get_circuit_breaker('test_service')
    cb.reset()

    # Open circuit by failing threshold times
    for _ in range(5):
        try:
            cb.call(lambda: self._raise_error())
        except:
            pass

    # Verify circuit is open
    assert cb.state == CircuitBreakerState.OPEN

    # Verify fails fast
    with pytest.raises(CircuitBreakerOpenError):
        cb.call(lambda: "should not execute")
```

## Troubleshooting

### Circuit Breaker Stuck Open
```python
# Manually reset circuit breaker
cb = get_circuit_breaker('anthropic_api')
cb.reset()
```

### Too Many Retries
```python
# Reduce retry attempts
@retry_with_backoff(max_attempts=2)  # Instead of 3
def function():
    pass
```

### High Latency from Retries
```python
# Reduce base delay
@retry_with_backoff(base_delay=1.0)  # Instead of 2.0
def function():
    pass
```

### Fallback Not Triggered
- Verify fallback strategy is configured
- Check error category (permanent errors don't retry)
- Review logs for error classification

## Summary

The error recovery system provides production-grade resilience for SuperAgent:

- ✅ Automatic retry with exponential backoff
- ✅ Circuit breakers prevent cascading failures
- ✅ Intelligent error categorization
- ✅ Graceful degradation for service outages
- ✅ Full observability integration
- ✅ Agent-specific recovery policies
- ✅ Comprehensive test coverage (37 unit tests)

All agents should use `@get_agent_recovery_decorator` for consistent error handling across the system.
