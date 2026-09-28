import asyncio
from datetime import datetime, timezone
from enum import Enum
import logging
from typing import Any, Callable, Coroutine, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class CircuitBreakerOpenException(Exception):
    pass


class UpstreamCircuitBreaker:
    """
    Lightweight in-memory circuit breaker for third-party scrapers and APIs.
    """

    def __init__(
        self,
        name: str = "upstream-flipp",
        failure_threshold: int = 3,
        recovery_timeout_seconds: float = 30.0,
        half_open_max_trials: int = 1,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout_seconds = recovery_timeout_seconds
        self.half_open_max_trials = half_open_max_trials

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_state_change = datetime.now(timezone.utc)
        self._half_open_trials = 0
        self._lock = asyncio.Lock()

    async def call(self, coro_func: Callable[..., Coroutine[Any, Any, T]], *args: Any, **kwargs: Any) -> T:
        async with self._lock:
            now = datetime.now(timezone.utc)
            if self.state == CircuitState.OPEN:
                elapsed = (now - self.last_state_change).total_seconds()
                if elapsed >= self.recovery_timeout_seconds:
                    logger.info("CircuitBreaker '%s' transitioned OPEN -> HALF_OPEN (probe attempt)", self.name)
                    self.state = CircuitState.HALF_OPEN
                    self._half_open_trials = 0
                else:
                    raise CircuitBreakerOpenException(
                        f"CircuitBreaker '{self.name}' is OPEN. Fast failing upstream call."
                    )

            if self.state == CircuitState.HALF_OPEN:
                if self._half_open_trials >= self.half_open_max_trials:
                    raise CircuitBreakerOpenException(
                        f"CircuitBreaker '{self.name}' is HALF_OPEN and busy with trial request."
                    )
                self._half_open_trials += 1

        try:
            result = await coro_func(*args, **kwargs)
            await self._on_success()
            return result
        except Exception as exc:
            await self._on_failure(exc)
            raise

    async def _on_success(self) -> None:
        async with self._lock:
            if self.state in (CircuitState.HALF_OPEN, CircuitState.CLOSED):
                if self.state == CircuitState.HALF_OPEN:
                    logger.info("CircuitBreaker '%s' probe succeeded. Transitioning HALF_OPEN -> CLOSED", self.name)
                self.failure_count = 0
                self.state = CircuitState.CLOSED

    async def _on_failure(self, exc: Exception) -> None:
        async with self._lock:
            self.failure_count += 1
            logger.warning(
                "CircuitBreaker '%s' recorded failure (%d/%d): %s",
                self.name,
                self.failure_count,
                self.failure_threshold,
                exc,
            )
            if self.failure_count >= self.failure_threshold:
                if self.state != CircuitState.OPEN:
                    logger.error(
                        "CircuitBreaker '%s' threshold reached. Transitioning to OPEN for %ss",
                        self.name,
                        self.recovery_timeout_seconds,
                    )
                    self.state = CircuitState.OPEN
                    self.last_state_change = datetime.now(timezone.utc)