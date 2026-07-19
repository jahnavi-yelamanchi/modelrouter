import time
from dataclasses import dataclass, field

from app.providers import ModelReply, OpenAICompatibleClient, ProviderError


@dataclass
class CircuitBreaker:
    failure_limit: int = 3
    reset_after_seconds: float = 30.0
    failures: int = 0
    opened_at: float | None = None

    def allow(self) -> bool:
        if self.opened_at is None:
            return True
        return time.monotonic() - self.opened_at >= self.reset_after_seconds

    def success(self) -> None:
        self.failures = 0
        self.opened_at = None

    def failure(self) -> None:
        self.failures += 1
        if self.failures >= self.failure_limit:
            self.opened_at = time.monotonic()

    @property
    def state(self) -> str:
        if self.opened_at is None:
            return "closed"
        return "half_open" if self.allow() else "open"


@dataclass
class Gateway:
    breakers: dict[str, CircuitBreaker] = field(
        default_factory=lambda: {"local": CircuitBreaker(), "remote": CircuitBreaker()}
    )

    def chat(
        self,
        providers: dict[str, OpenAICompatibleClient],
        preferred: str,
        messages: list[dict[str, str]],
    ) -> tuple[ModelReply, str, list[str]]:
        attempted: list[str] = []
        for route in (preferred, "remote" if preferred == "local" else "local"):
            breaker = self.breakers[route]
            if not breaker.allow():
                attempted.append(f"{route}:circuit_open")
                continue
            try:
                reply = providers[route].chat(messages)
            except ProviderError as error:
                breaker.failure()
                attempted.append(f"{route}:failed")
                last_error = error
                continue
            breaker.success()
            attempted.append(f"{route}:ok")
            return reply, route, attempted
        raise ProviderError(f"all routes unavailable: {attempted}") from locals().get("last_error")
