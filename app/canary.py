import hashlib
import os
from dataclasses import dataclass

from app.metrics import Metrics


@dataclass(frozen=True)
class Policy:
    threshold: float
    name: str


class Canary:
    def __init__(self, metrics: Metrics) -> None:
        self.metrics = metrics
        self.percent = int(os.getenv("CANARY_PERCENT", "5"))
        self.threshold = float(os.getenv("CANARY_RISK_THRESHOLD", "0.55"))

    def policy(self, request_id: str, control_threshold: float = 0.45) -> Policy:
        bucket = int(hashlib.sha256(request_id.encode()).hexdigest(), 16) % 100
        if bucket < self.percent and self.metrics.canary_safe():
            return Policy(self.threshold, "canary")
        return Policy(control_threshold, "control")
