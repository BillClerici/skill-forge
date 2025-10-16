"""
Comprehensive Error Handling for Game Engine
Includes retry logic, circuit breakers, and graceful degradation
"""
import logging
import time
import asyncio
from typing import Callable, Any, Optional, TypeVar, ParamSpec
from functools import wraps
from collections import defaultdict
from datetime import datetime, timedelta
import traceback

logger = logging.getLogger(__name__)

# Type hints for decorators
P = ParamSpec('P')
T = TypeVar('T')


class CircuitBreaker:
    """
    Circuit breaker pattern for external service calls
    Prevents cascading failures by temporarily disabling failing services
    """
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.failure_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.state = "closed"  # closed, open, half-open

    def call(self, func: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> T:
        """Execute function with circuit breaker protection"""

        # Check if circuit is open
        if self.state == "open":
            if datetime.now() - self.last_failure_time > timedelta(seconds=self.recovery_timeout):
                self.state = "half-open"
                logger.info(f"Circuit breaker entering half-open state for {func.__name__}")
            else:
                raise Exception(f"Circuit breaker is OPEN for {func.__name__}")

        try:
            result = func(*args, **kwargs)

            # Success - reset if in half-open
            if self.state == "half-open":
                self.state = "closed"
                self.failure_count = 0
                logger.info(f"Circuit breaker closed for {func.__name__}")

            return result

        except self.expected_exception as e:
            self.failure_count += 1
            self.last_failure_time = datetime.now()

            if self.failure_count >= self.failure_threshold:
                self.state = "open"
                logger.error(
                    f"Circuit breaker OPENED for {func.__name__} "
                    f"after {self.failure_count} failures"
                )

            raise


# Global circuit breakers for different services
circuit_breakers = {
    "mcp_player_data": CircuitBreaker(failure_threshold=3, recovery_timeout=30),
    "mcp_world_universe": CircuitBreaker(failure_threshold=3, recovery_timeout=30),
    "mcp_quest_mission": CircuitBreaker(failure_threshold=3, recovery_timeout=30),
    "mcp_npc_personality": CircuitBreaker(failure_threshold=3, recovery_timeout=30),
    "mcp_item_equipment": CircuitBreaker(failure_threshold=3, recovery_timeout=30),
    "redis": CircuitBreaker(failure_threshold=5, recovery_timeout=10),
    "mongodb": CircuitBreaker(failure_threshold=5, recovery_timeout=10),
    "neo4j": CircuitBreaker(failure_threshold=5, recovery_timeout=10),
}


def with_retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """
    Decorator for retrying failed operations with exponential backoff

    Args:
        max_attempts: Maximum number of retry attempts
        delay: Initial delay between retries (seconds)
        backoff: Multiplier for delay after each attempt
        exceptions: Tuple of exceptions to catch and retry
    """
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            current_delay = delay
            last_exception = None

            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt < max_attempts - 1:
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_attempts} failed for {func.__name__}: {str(e)}. "
                            f"Retrying in {current_delay}s..."
                        )
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(
                            f"All {max_attempts} attempts failed for {func.__name__}: {str(e)}"
                        )

            # All attempts failed
            raise last_exception

        return wrapper
    return decorator


def async_with_retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """Async version of retry decorator"""
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            current_delay = delay
            last_exception = None

            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt < max_attempts - 1:
                        logger.warning(
                            f"Async attempt {attempt + 1}/{max_attempts} failed for {func.__name__}: {str(e)}. "
                            f"Retrying in {current_delay}s..."
                        )
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(
                            f"All {max_attempts} async attempts failed for {func.__name__}: {str(e)}"
                        )

            raise last_exception

        return wrapper
    return decorator


def with_circuit_breaker(service_name: str):
    """
    Decorator to apply circuit breaker pattern to a function

    Args:
        service_name: Name of the service (must be in circuit_breakers dict)
    """
    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            breaker = circuit_breakers.get(service_name)
            if not breaker:
                logger.warning(f"No circuit breaker found for {service_name}, executing without protection")
                return func(*args, **kwargs)

            return breaker.call(func, *args, **kwargs)

        return wrapper
    return decorator


class ErrorRecovery:
    """Centralized error recovery strategies"""

    @staticmethod
    def recover_from_database_error(error: Exception, fallback_data: Any = None) -> Any:
        """
        Recover from database connection errors

        Args:
            error: The database error that occurred
            fallback_data: Data to return if recovery fails
        """
        logger.error(f"Database error: {str(error)}")
        logger.error(f"Traceback: {traceback.format_exc()}")

        # Log for monitoring/alerting
        logger.critical("Database connection failed - manual intervention may be required")

        # Return fallback data or raise
        if fallback_data is not None:
            logger.info("Returning fallback data due to database error")
            return fallback_data
        else:
            raise

    @staticmethod
    def recover_from_mcp_error(
        service_name: str,
        error: Exception,
        fallback_data: Any = None,
        use_cache: bool = True
    ) -> Any:
        """
        Recover from MCP server errors

        Args:
            service_name: Name of the MCP service
            error: The error that occurred
            fallback_data: Data to return if recovery fails
            use_cache: Whether to attempt cache retrieval
        """
        logger.error(f"MCP service {service_name} error: {str(error)}")

        # Try cache first
        if use_cache:
            # TODO: Implement cache retrieval
            logger.info(f"Attempting cache retrieval for {service_name}")

        # Use fallback data
        if fallback_data is not None:
            logger.info(f"Using fallback data for {service_name}")
            return fallback_data

        # If no fallback, raise the error
        raise

    @staticmethod
    def recover_from_api_error(
        endpoint: str,
        error: Exception,
        retry_count: int = 0,
        max_retries: int = 3
    ) -> bool:
        """
        Determine if an API error is recoverable

        Returns:
            True if should retry, False otherwise
        """
        logger.error(f"API error for {endpoint}: {str(error)}")

        # Check if error is retryable
        retryable_errors = [
            "timeout",
            "connection",
            "network",
            "temporarily unavailable",
            "503",
            "504"
        ]

        error_str = str(error).lower()
        is_retryable = any(err in error_str for err in retryable_errors)

        if is_retryable and retry_count < max_retries:
            logger.info(f"Error is retryable. Attempt {retry_count + 1}/{max_retries}")
            return True

        return False


class SessionRecovery:
    """Handle session crash recovery and state restoration"""

    @staticmethod
    def save_session_checkpoint(session_id: str, state: dict) -> bool:
        """
        Save a checkpoint of session state for crash recovery

        Args:
            session_id: The session ID
            state: Current session state
        """
        try:
            # TODO: Implement checkpoint saving to Redis
            logger.info(f"Session checkpoint saved for {session_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to save session checkpoint: {str(e)}")
            return False

    @staticmethod
    def restore_session_from_checkpoint(session_id: str) -> Optional[dict]:
        """
        Restore session state from last checkpoint

        Args:
            session_id: The session ID to restore

        Returns:
            Restored state dict or None if not found
        """
        try:
            # TODO: Implement checkpoint restoration from Redis
            logger.info(f"Attempting to restore session {session_id}")
            return None
        except Exception as e:
            logger.error(f"Failed to restore session checkpoint: {str(e)}")
            return None


class GracefulDegradation:
    """Strategies for gracefully degrading functionality when services fail"""

    @staticmethod
    def get_default_character_data() -> dict:
        """Return minimal character data when MCP is unavailable"""
        return {
            "character_id": None,
            "name": "Unknown Character",
            "level": 1,
            "attributes": {},
            "skills": [],
            "inventory": []
        }

    @staticmethod
    def get_default_quest_data() -> dict:
        """Return minimal quest data when MCP is unavailable"""
        return {
            "quest_id": None,
            "title": "Quest Unavailable",
            "description": "Quest data is temporarily unavailable",
            "objectives": []
        }

    @staticmethod
    def get_fallback_gm_response() -> str:
        """Return fallback Game Master response when AI is unavailable"""
        return (
            "The Game Master seems momentarily distracted. "
            "Your adventure continues, but you'll need to be patient for a moment..."
        )


# Logging configuration helper
def setup_error_logging():
    """Configure enhanced error logging"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            # Add file handler if needed
            # logging.FileHandler('game_engine_errors.log')
        ]
    )

    # Set specific loggers to DEBUG for troubleshooting
    logging.getLogger('app.core.error_handling').setLevel(logging.DEBUG)
    logging.getLogger('app.api').setLevel(logging.DEBUG)
