import json
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from starlette.responses import StreamingResponse

from app.agent import investigate, set_provider
from app.config import DEFAULT_PROVIDER, PROVIDERS
from app.history import get_investigation, list_investigations, save_investigation

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="SRE Investigation Agent")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

set_provider(DEFAULT_PROVIDER)


class InvestigateRequest(BaseModel):
    alert: str
    provider: str | None = None
    model: str | None = None


@app.post("/investigate")
async def run_investigation(req: InvestigateRequest):
    if req.provider and req.provider in PROVIDERS:
        set_provider(req.provider, req.model)

    def event_stream():
        events = []
        conclusion = ""

        for event in investigate(req.alert):
            events.append(event)
            if event["type"] == "conclusion":
                conclusion = event.get("content", "")
            yield f"data: {json.dumps(event, default=str)}\n\n"

        save_investigation(req.alert, conclusion, events)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/providers")
async def get_providers():
    return {
        name: {"models": cfg["models"], "default_model": cfg["default_model"]}
        for name, cfg in PROVIDERS.items()
    }


@app.get("/history")
async def history():
    return list_investigations()


@app.get("/investigations/{inv_id}")
async def get_inv(inv_id: int):
    result = get_investigation(inv_id)
    if not result:
        return {"error": "not found"}
    return result


@app.get("/health")
async def health():
    return {"status": "ok"}
