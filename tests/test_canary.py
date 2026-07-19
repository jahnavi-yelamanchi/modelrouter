import os
import tempfile
import unittest

from app.canary import Canary
from app.metrics import Event, Metrics


class CanaryTest(unittest.TestCase):
    def test_rolls_back_after_labeled_quality_regression(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            os.environ["CANARY_PERCENT"] = "100"
            os.environ["CANARY_MIN_EVALUATIONS"] = "1"
            metrics = Metrics(f"{directory}/metrics.db")
            metrics.record(Event("control", "control", "remote", "remote", False, 0.2, 0, 0))
            metrics.evaluate("control", 0.2, 0.9)
            metrics.record(Event("canary", "canary", "local", "local", False, 0.2, 0, 0))
            metrics.evaluate("canary", 0.2, 0.9)
            self.assertEqual(Canary(metrics).policy("another").name, "control")
