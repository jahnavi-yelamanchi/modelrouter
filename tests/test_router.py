import unittest

from app.router import choose_route


class RouterTest(unittest.TestCase):
    def test_router_escalates_code_and_keeps_simple_requests_local(self) -> None:
        simple = choose_route([{"role": "user", "content": "What is the capital of France?"}])
        code = choose_route([{"role": "user", "content": "Explain this Python algorithm and fix its bug."}])
        self.assertEqual(simple.route, "local")
        self.assertEqual(code.route, "remote")
