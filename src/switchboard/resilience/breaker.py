import asyncio
import time
from collections.abc import Awaitable, Callable
from enum import Enum
from typing import TypeVar

T = TypeVar("T")


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(Exception):
    pass


class CircuitBreaker:
    def __init__(
        self,
        *,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._clock = clock
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._opened_at: float | None = None
        self._half_open_trial_in_flight = False
        self._lock = asyncio.Lock()

    def _compute_state(self) -> CircuitState:
        if (
            self._state == CircuitState.OPEN
            and self._opened_at is not None
            and self._clock() - self._opened_at >= self._recovery_timeout
        ):
            return CircuitState.HALF_OPEN
        return self._state

    @property
    def state(self) -> CircuitState:
        return self._compute_state()

    async def before_call(self) -> None:
        async with self._lock:
            current = self._compute_state()
            if current == CircuitState.OPEN:
                raise CircuitOpenError()
            if current == CircuitState.HALF_OPEN:
                if self._half_open_trial_in_flight:
                    raise CircuitOpenError()
                self._half_open_trial_in_flight = True

    async def on_success(self) -> None:
        async with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._opened_at = None
            self._half_open_trial_in_flight = False

    async def on_failure(self) -> None:
        async with self._lock:
            if self._half_open_trial_in_flight:
                self._state = CircuitState.OPEN
                self._opened_at = self._clock()
                self._half_open_trial_in_flight = False
                return
            self._failure_count += 1
            if self._failure_count >= self._failure_threshold:
                self._state = CircuitState.OPEN
                self._opened_at = self._clock()

    async def call(
        self, func: Callable[[], Awaitable[T]], *, failure_exceptions: tuple[type[Exception], ...]
    ) -> T:
        await self.before_call()
        try:
            result = await func()
        except failure_exceptions:
            await self.on_failure()
            raise
        else:
            await self.on_success()
            return result