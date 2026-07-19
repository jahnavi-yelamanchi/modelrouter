import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path


def _rate(name: str) -> float:
    return float(os.getenv(name, "0")) / 1_000_000


def request_cost(route: str, prompt_tokens: int, completion_tokens: int) -> float:
    prefix = route.upper()
    return round(
        prompt_tokens * _rate(f"{prefix}_INPUT_PER_MILLION")
        + completion_tokens * _rate(f"{prefix}_OUTPUT_PER_MILLION"),
        8,
    )


@dataclass(frozen=True)
class Event:
    request_id: str
    intended_route: str
    executed_route: str
    fallback: bool
    quality_risk: float
    prompt_tokens: int
    completion_tokens: int


class Metrics:
    def __init__(self, database: str | None = None) -> None:
        self.database = database or os.getenv("METRICS_DB", "/data/router.db")
        Path(self.database).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS events (
                    request_id TEXT PRIMARY KEY,
                    intended_route TEXT NOT NULL,
                    executed_route TEXT NOT NULL,
                    fallback INTEGER NOT NULL,
                    quality_risk REAL NOT NULL,
                    delivery_cost REAL NOT NULL,
                    remote_baseline_cost REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS evaluations (
                    request_id TEXT PRIMARY KEY REFERENCES events(request_id),
                    local_score REAL NOT NULL,
                    remote_score REAL NOT NULL
                );
                """
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database)

    def record(self, event: Event) -> dict[str, float]:
        delivery_cost = request_cost(event.executed_route, event.prompt_tokens, event.completion_tokens)
        remote_baseline_cost = request_cost("remote", event.prompt_tokens, event.completion_tokens)
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO events VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    event.request_id,
                    event.intended_route,
                    event.executed_route,
                    event.fallback,
                    event.quality_risk,
                    delivery_cost,
                    remote_baseline_cost,
                ),
            )
        return {"used": delivery_cost, "saved": round(remote_baseline_cost - delivery_cost, 8)}

    def evaluate(self, request_id: str, local_score: float, remote_score: float) -> None:
        if not all(0 <= score <= 1 for score in (local_score, remote_score)):
            raise ValueError("scores must be between 0 and 1")
        with self._connect() as connection:
            connection.execute("INSERT OR REPLACE INTO evaluations VALUES (?, ?, ?)", (request_id, local_score, remote_score))

    def summary(self) -> dict[str, float | int | None]:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT COUNT(*), COALESCE(SUM(delivery_cost), 0),
                       COALESCE(SUM(remote_baseline_cost - delivery_cost), 0),
                       COALESCE(SUM(fallback), 0),
                       AVG(remote_score - local_score)
                FROM events LEFT JOIN evaluations USING (request_id)
                """
            ).fetchone()
        return {
            "requests": row[0],
            "cost_used_usd": round(row[1], 8),
            "cost_saved_usd": round(row[2], 8),
            "fallbacks": row[3],
            "quality_delta_remote_minus_local": None if row[4] is None else round(row[4], 4),
        }
