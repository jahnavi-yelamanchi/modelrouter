from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.providers import ProviderError, clients

app = FastAPI(title="Model Router")


class Message(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1)


class ChatRequest(BaseModel):
    messages: list[Message] = Field(min_length=1)
    route: Literal["local", "remote"] = "remote"


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/chat")
def chat(request: ChatRequest) -> dict[str, object]:
    client = clients()[request.route]
    try:
        reply = client.chat([message.model_dump() for message in request.messages])
    except ProviderError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    return {
        "content": reply.content,
        "route": request.route,
        "usage": {
            "prompt_tokens": reply.prompt_tokens,
            "completion_tokens": reply.completion_tokens,
        },
    }
