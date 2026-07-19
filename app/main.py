from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.providers import ProviderError, clients
from app.router import choose_route

app = FastAPI(title="Model Router")


class Message(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1)


class ChatRequest(BaseModel):
    messages: list[Message] = Field(min_length=1)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/chat")
def chat(request: ChatRequest) -> dict[str, object]:
    message_data = [message.model_dump() for message in request.messages]
    decision = choose_route(message_data)
    client = clients()[decision.route]
    try:
        reply = client.chat(message_data)
    except ProviderError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    return {
        "content": reply.content,
        "route": decision.route,
        "decision": {
            "intent": decision.intent,
            "complexity": decision.complexity,
            "uncertainty": decision.uncertainty,
            "quality_risk": decision.quality_risk,
            "reason": decision.reason,
        },
        "usage": {
            "prompt_tokens": reply.prompt_tokens,
            "completion_tokens": reply.completion_tokens,
        },
    }
