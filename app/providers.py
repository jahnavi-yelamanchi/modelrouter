import json
import os
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class ProviderError(Exception):
    pass


@dataclass(frozen=True)
class ModelReply:
    content: str
    prompt_tokens: int
    completion_tokens: int


class OpenAICompatibleClient:
    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model

    def chat(self, messages: list[dict[str, str]]) -> ModelReply:
        body = json.dumps({"model": self.model, "messages": messages}).encode()
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request = Request(f"{self.base_url}/chat/completions", body, headers=headers)
        try:
            with urlopen(request, timeout=30) as response:  # noqa: S310
                payload = json.load(response)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
            raise ProviderError(f"{self.model}: {error}") from error
        try:
            usage = payload.get("usage", {})
            return ModelReply(
                content=payload["choices"][0]["message"]["content"],
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
            )
        except (KeyError, IndexError, TypeError) as error:
            raise ProviderError(f"{self.model}: malformed response") from error


def clients() -> dict[str, OpenAICompatibleClient]:
    return {
        "local": OpenAICompatibleClient(
            os.getenv("LOCAL_BASE_URL", "http://ollama:11434/v1"),
            os.getenv("LOCAL_API_KEY", ""),
            os.getenv("LOCAL_MODEL", "qwen2.5:1.5b"),
        ),
        "remote": OpenAICompatibleClient(
            os.getenv("REMOTE_BASE_URL", "https://api.openai.com/v1"),
            os.getenv("REMOTE_API_KEY", ""),
            os.getenv("REMOTE_MODEL", "gpt-4.1-mini"),
        ),
    }
