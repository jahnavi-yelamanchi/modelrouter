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
    policy: str
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
                    policy TEXT NOT NULL DEFAULT 'control',
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
            columns = {row[1] for row in connection.execute("PRAGMA table_info(events)")}
            if "policy" not in columns:
                connection.execute("ALTER TABLE events ADD COLUMN policy TEXT NOT NULL DEFAULT 'control'")

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database)

    def record(self, event: Event) -> dict[str, float]:
        delivery_cost = request_cost(event.executed_route, event.prompt_tokens, event.completion_tokens)
        remote_baseline_cost = request_cost("remote", event.prompt_tokens, event.completion_tokens)
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO events (request_id, policy, intended_route, executed_route, fallback, quality_risk, delivery_cost, remote_baseline_cost) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    event.request_id,
                    event.policy,
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
                       AVG(remote_score - local_score),
                       COALESCE(SUM(policy = 'canary'), 0)
                FROM events LEFT JOIN evaluations USING (request_id)
                """
            ).fetchone()
        return {
            "requests": row[0],
            "cost_used_usd": round(row[1], 8),
            "cost_saved_usd": round(row[2], 8),
            "fallbacks": row[3],
            "quality_delta_remote_minus_local": None if row[4] is None else round(row[4], 4),
            "canary_requests": row[5],
        }

    def canary_safe(self) -> bool:
        minimum = int(os.getenv("CANARY_MIN_EVALUATIONS", "20"))
        tolerance = float(os.getenv("CANARY_MAX_QUALITY_REGRESSION", "0.03"))
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT policy, COUNT(*), AVG(CASE executed_route
                    WHEN 'local' THEN local_score ELSE remote_score END)
                FROM events JOIN evaluations USING (request_id)
                GROUP BY policy
                """
            ).fetchall()
        scores = {policy: (count, score) for policy, count, score in rows}
        if "canary" not in scores or scores["canary"][0] < minimum or "control" not in scores:
            return True
        return scores["canary"][1] >= scores["control"][1] - tolerance
