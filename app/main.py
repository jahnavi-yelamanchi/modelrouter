from fastapi import FastAPI

app = FastAPI(title="Model Router")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
