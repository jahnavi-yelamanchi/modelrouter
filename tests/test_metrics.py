import os
import tempfile
import unittest

from app.metrics import Event, Metrics


class MetricsTest(unittest.TestCase):
    def test_records_remote_baseline_savings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            previous = os.environ.get("REMOTE_INPUT_PER_MILLION")
            os.environ["REMOTE_INPUT_PER_MILLION"] = "1000000"
            try:
                metrics = Metrics(f"{directory}/metrics.db")
                cost = metrics.record(Event("one", "control", "local", "local", False, 0.1, 3, 0))
                self.assertEqual(cost, {"used": 0.0, "saved": 3.0})
                self.assertEqual(metrics.summary()["cost_saved_usd"], 3.0)
            finally:
                if previous is None:
                    del os.environ["REMOTE_INPUT_PER_MILLION"]
                else:
                    os.environ["REMOTE_INPUT_PER_MILLION"] = previous
