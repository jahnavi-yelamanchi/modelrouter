from dataclasses import dataclass


INTENTS = {
    "code": ("code", "python", "bug", "function", "api", "algorithm"),
    "research": ("research", "paper", "cite", "evidence", "compare"),
    "reasoning": ("prove", "derive", "math", "calculate", "explain why"),
    "creative": ("write", "draft", "poem", "story", "brainstorm"),
}
COMPLEXITY_SIGNALS = INTENTS["code"] + INTENTS["research"] + INTENTS["reasoning"]


@dataclass(frozen=True)
class RouteDecision:
    route: str
    intent: str
    complexity: float
    uncertainty: float
    quality_risk: float
    reason: str


def classify(text: str) -> tuple[str, float, float]:
    lowered = text.lower()
    intent = next((name for name, words in INTENTS.items() if any(word in lowered for word in words)), "general")
    matches = sum(word in lowered for word in COMPLEXITY_SIGNALS)
    complexity = min(1.0, 0.15 + len(text.split()) / 250 + matches * 0.2)
    uncertainty = 0.55 if intent == "general" else 0.15
    if text.count("?") > 1:
        uncertainty += 0.1
    return intent, complexity, min(1.0, uncertainty)


def choose_route(messages: list[dict[str, str]], threshold: float = 0.45) -> RouteDecision:
    text = "\n".join(message["content"] for message in messages if message["role"] == "user")
    intent, complexity, uncertainty = classify(text)
    quality_risk = round(min(1.0, complexity * 0.7 + uncertainty * 0.3), 3)
    if quality_risk >= threshold:
        return RouteDecision("remote", intent, complexity, uncertainty, quality_risk, "risk_above_threshold")
    return RouteDecision("local", intent, complexity, uncertainty, quality_risk, "low_risk")
