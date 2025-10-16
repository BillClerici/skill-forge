# Error Handling System

## Overview

The SkillForge game engine includes a comprehensive error handling system with retry logic, circuit breakers, and graceful degradation to ensure reliable operation even when external services fail.

## Features

### 1. Retry Logic with Exponential Backoff

Automatically retries failed operations with configurable delays:

```python
from app.core.error_handling import with_retry, async_with_retry

@with_retry(max_attempts=3, delay=1.0, backoff=2.0)
def fetch_data():
    # Your code here
    pass

@async_with_retry(max_attempts=3, delay=0.5)
async def fetch_data_async():
    # Your async code here
    pass
```

### 2. Circuit Breaker Pattern

Prevents cascading failures by temporarily disabling failing services:

```python
from app.core.error_handling import with_circuit_breaker

@with_circuit_breaker("mcp_player_data")
def call_mcp_service():
    # Service call here
    pass
```

**Circuit States:**
- **Closed**: Normal operation, requests pass through
- **Open**: Service is failing, requests are blocked (returns immediately)
- **Half-Open**: Testing if service recovered after timeout

**Configuration:**
- Failure threshold: 3-5 failures trigger circuit open
- Recovery timeout: 10-60 seconds before retry
- Per-service circuit breakers for each MCP server and database

### 3. Graceful Degradation

When services fail, fallback to default data:

```python
from app.core.error_handling import GracefulDegradation

# Returns minimal character data
default_character = GracefulDegradation.get_default_character_data()

# Returns fallback quest data
default_quest = GracefulDegradation.get_default_quest_data()

# Returns friendly DM message
fallback_message = GracefulDegradation.get_fallback_dm_response()
```

### 4. Session Recovery

Auto-save and crash recovery for game sessions:

```python
from app.core.error_handling import SessionRecovery

# Save checkpoint
SessionRecovery.save_session_checkpoint(session_id, state)

# Restore from checkpoint
restored_state = SessionRecovery.restore_session_from_checkpoint(session_id)
```

## MCP Client Error Handling

The MCP client (`app/services/mcp_client.py`) includes:

1. **Automatic Retries**: 3 attempts with 0.5s exponential backoff
2. **Fallback Data**: Returns default data when MCP servers unavailable
3. **Detailed Logging**: All failures logged with context

**Example:**
```python
# Automatically retries and falls back to default data
character = await mcp_client.get_character_info(character_id)
# Returns default character data if MCP unavailable
```

## WebSocket Reconnection

Frontend automatically reconnects WebSocket connections (see `templates/game/session.html`):

```javascript
ws.onclose = function() {
    connectionStatus.textContent = 'Disconnected';
    // Automatic reconnection after 3 seconds
    setTimeout(connectWebSocket, 3000);
};
```

## Error Recovery Strategies

### Database Errors

```python
from app.core.error_handling import ErrorRecovery

try:
    result = query_database()
except DatabaseError as e:
    result = ErrorRecovery.recover_from_database_error(
        error=e,
        fallback_data=default_data
    )
```

### MCP Service Errors

```python
try:
    data = await mcp_client.get_quest(quest_id)
except Exception as e:
    data = ErrorRecovery.recover_from_mcp_error(
        service_name="mcp_quest_mission",
        error=e,
        fallback_data=GracefulDegradation.get_default_quest_data()
    )
```

### API Errors

```python
if ErrorRecovery.recover_from_api_error(
    endpoint="/api/session/start",
    error=e,
    retry_count=current_attempt,
    max_retries=3
):
    # Retry the operation
    retry_request()
```

## Logging

All errors are logged with structured context:

```python
logger.error(
    "mcp_get_failed",
    server=server,
    endpoint=endpoint,
    error=str(e)
)
```

**Log Levels:**
- `DEBUG`: Detailed retry attempts
- `INFO`: Circuit breaker state changes, recoveries
- `WARNING`: Retryable failures
- `ERROR`: Final failures after all retries
- `CRITICAL`: System-level failures requiring intervention

## Monitoring

Key metrics to monitor:

1. **Circuit Breaker States**: Alert when circuits open
2. **Retry Counts**: Track how often retries are needed
3. **Fallback Usage**: Monitor graceful degradation frequency
4. **Error Rates**: Per-service error percentages

## Configuration

Edit circuit breaker settings in `app/core/error_handling.py`:

```python
circuit_breakers = {
    "mcp_player_data": CircuitBreaker(
        failure_threshold=3,    # Failures before opening
        recovery_timeout=30,    # Seconds before retry
    ),
    # ... more services
}
```

## Best Practices

1. **Always use retry decorators** for external service calls
2. **Provide fallback data** when possible for graceful degradation
3. **Log with context** to aid debugging
4. **Monitor circuit breaker states** for service health
5. **Test failure scenarios** to verify recovery works

## Testing Failure Scenarios

To test error handling:

```bash
# Stop MCP service to trigger circuit breaker
docker stop skillforge-mcp-player-data

# Make API call - should fallback gracefully
curl http://localhost:9500/api/v1/session/start-solo

# Restart service - circuit should close
docker start skillforge-mcp-player-data
```

## Future Enhancements

- [ ] Implement session checkpoint save/restore in Redis
- [ ] Add distributed tracing for error tracking
- [ ] Create health check dashboard
- [ ] Add automated alerting for circuit breaker opens
- [ ] Implement request queueing during service outages
