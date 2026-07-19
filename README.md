# Model Router

A Dockerized, cost-aware LLM gateway. It routes low-risk requests to a small local Ollama model and escalates complex or uncertain requests to a stronger API model. There is no web UI.

## What is different here

Most routing demos stop at a classifier. This project treats routing as an auditable online decision:

\[
\text{route}(x)=\begin{cases}
\text{remote}, & \hat r(x)\ge\tau\\
\text{local}, & \hat r(x)<\tau
\end{cases}
\]

`\hat r(x)` combines transparent complexity and uncertainty features. The response reports the decision, and the gateway records its actual provider choice, fallback, delivery cost, and remote-baseline saving. New thresholds enter through a deterministic canary; the candidate shuts off after sufficiently many independently scored examples show a configured quality regression.

This is an **engineering contribution**, not a claim of a new routing theorem. It operationalizes three research ideas:

- [FrugalGPT](https://arxiv.org/abs/2305.05176) establishes that cascades can reduce LLM inference cost while retaining quality.
- [RouteLLM](https://arxiv.org/abs/2406.18665) learns strong-versus-weak routing from preference data. Here, the deliberately small, interpretable policy makes the decision and its rollout observable for a Docker deployment.
- [Conformal Risk Control](https://arxiv.org/abs/2208.02814) motivates calibrating the escalation threshold on held-out labeled requests. This repository exposes the needed paired-quality data and canary guardrail; it does **not** claim distribution-free guarantees until `τ` is calibrated on exchangeable held-out data.

The honest novelty sentence for a presentation is: **“Model Router couples an interpretable risk gate with cost accounting, failure recovery, and evidence-gated canary rollout, so routing policy changes are measurable and reversible rather than static.”**

## Metrics and scientific limits

- `cost_used_usd` is the executed provider cost using token counts and the rates in `.env`.
- `cost_saved_usd` is the remote-baseline cost for the same observed token counts minus actual delivery cost.
- `quality_delta_remote_minus_local` is the mean of independently recorded paired scores. Positive means remote scored higher.
- Local cost defaults to zero and excludes hardware/energy depreciation. Set its rates if that matters.
- Quality delta remains `null` until both answers are evaluated. The gateway refuses to pretend a routing confidence score is a measured quality score.

## Run

```sh
cp .env.example .env
# Set REMOTE_API_KEY and your provider contract rates in .env.
docker compose --profile local up --build -d
docker compose exec ollama ollama pull qwen2.5:1.5b
./scripts/demo.sh
```

`REMOTE_BASE_URL` is OpenAI-compatible, so the stronger model can be any compatible paid API. The local route uses Ollama's compatible endpoint.

Endpoints:

- `POST /v1/chat` routes a chat request and returns route evidence and request cost.
- `GET /v1/metrics` returns cost used/saved, fallbacks, canary traffic, and measured quality delta.
- `POST /v1/evaluations/{request_id}` accepts independent `local_score` and `remote_score` values in `[0,1]` for paired evaluation.

Example evaluation after generating both responses for the same prompt:

```sh
curl -X POST http://localhost:8080/v1/evaluations/demo-simple \
  -H 'content-type: application/json' \
  -d '{"local_score":0.8,"remote_score":0.9}'
```

## Demo capture

1. Start the containers and run `./scripts/demo.sh` in a full-screen terminal.
2. Run `curl -sS http://localhost:8080/v1/metrics` once more after a few requests. Use this as the screenshot: it visibly proves route decisions, spend, savings, and canary state without a website.
3. Record a 60–90 second terminal session with macOS **Shift-Command-5**. State the simple/complex routing decision, show a forced provider outage for fallback if desired, then finish on `/v1/metrics`.
4. For a picture/video of you, use your webcam alongside that terminal recording. I cannot truthfully fabricate your likeness without a reference image.

## Checks

```sh
python3 -m unittest discover -s tests -v
docker build -t modelrouter:check .
```
