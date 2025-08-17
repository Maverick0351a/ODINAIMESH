# path: apps/gateway/odin_gateway/api_gateway.py
from __future__ import annotations

from fastapi import FastAPI, Request, Response
from pydantic import BaseModel
from prometheus_client import (
	CONTENT_TYPE_LATEST,
	CollectorRegistry,
	Counter,
	Histogram,
	generate_latest,
)
import time

from .translate import router as translate_router

app = FastAPI(title="ODIN Gateway", version="0.0.1")
app.include_router(translate_router)

# --- simple metrics ---
REG = CollectorRegistry(auto_describe=True)
REQS = Counter("odin_http_requests_total", "gateway requests", ["path", "method"], registry=REG)
LAT = Histogram("odin_http_request_seconds", "gateway latency", ["path", "method"], registry=REG)


@app.middleware("http")
async def metrics_mw(request: Request, call_next):
	start = time.perf_counter()
	try:
		resp = await call_next(request)
		return resp
	finally:
		LAT.labels(request.url.path, request.method).observe(time.perf_counter() - start)
		REQS.labels(request.url.path, request.method).inc()


@app.get("/health")
def health():
	return {"ok": True, "service": "gateway"}


@app.get("/metrics")
def metrics():
	return Response(content=generate_latest(REG), media_type=CONTENT_TYPE_LATEST)


class EchoIn(BaseModel):
	message: str


@app.post("/v1/echo")
def echo(body: EchoIn):
	return {"echo": body.message}
