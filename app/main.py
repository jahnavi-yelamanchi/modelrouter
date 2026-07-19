from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.canary import Canary
from app.metrics import Event, Metrics
from app.providers import ProviderError, clients
from app.reliability import Gateway
from app.router import choose_route

app = FastAPI(title="Model Router")
gateway = Gateway()
metrics = Metrics()
canary = Canary(metrics)


class Message(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1)


class ChatRequest(BaseModel):
    messages: list[Message] = Field(min_length=1)
    request_id: str | None = None


class Evaluation(BaseModel):
    local_score: float = Field(ge=0, le=1)
    remote_score: float = Field(ge=0, le=1)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/v1/chat")
def chat(request: ChatRequest) -> dict[str, object]:
    message_data = [message.model_dump() for message in request.messages]
    request_id = request.request_id or str(uuid4())
    policy = canary.policy(request_id)
    decision = choose_route(message_data, policy.threshold)
    try:
        reply, route, attempted = gateway.chat(clients(), decision.route, message_data)
    except ProviderError as error:
        raise HTTPException(status_code=502, detail=str(error)) from error
    cost = metrics.record(
        Event(
            request_id=request_id,
            policy=policy.name,
            intended_route=decision.route,
            executed_route=route,
            fallback=route != decision.route,
            quality_risk=decision.quality_risk,
            prompt_tokens=reply.prompt_tokens,
            completion_tokens=reply.completion_tokens,
        )
    )
    return {
        "request_id": request_id,
        "content": reply.content,
        "route": route,
        "fallback": route != decision.route,
        "policy": policy.name,
        "attempted": attempted,
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
        "cost_usd": cost,
    }


@app.get("/v1/metrics")
def get_metrics() -> dict[str, float | int | None]:
    return metrics.summary()


@app.post("/v1/evaluations/{request_id}")
def record_evaluation(request_id: str, evaluation: Evaluation) -> dict[str, str]:
    metrics.evaluate(request_id, evaluation.local_score, evaluation.remote_score)
    return {"status": "recorded"}
