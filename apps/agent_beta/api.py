from __future__ import annotations

from fastapi import FastAPI, HTTPException, Depends, Request, Response
from typing import Any, Dict
import re

from libs.odin_core.odin import sft_beta
from .security import require_http_signature
from .metrics import REG, REQS, LAT, CONTENT_TYPE_LATEST, generate_latest
import time

app = FastAPI(title="Agent Beta", version="0.1.0")


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
    return {"ok": True, "service": "agent-beta"}


@app.get("/metrics")
def metrics():
    return Response(content=generate_latest(REG), media_type=CONTENT_TYPE_LATEST)


@app.post("/task", dependencies=[Depends(require_http_signature)])
def task(req: Dict[str, Any]):
    # Enforce expected intent
    if req.get("intent") != "beta.request":
        raise HTTPException(status_code=400, detail="expected intent 'beta.request'")

    # Structured task/args path (no SFT validation here to allow minimal fields)
    if "task" in req and "args" in req:
        task_name = req.get("task")
        args = req.get("args") or {}
        if not isinstance(args, dict):
            raise HTTPException(status_code=422, detail={"error": "beta.args.invalid"})
        if task_name == "math.add":
            try:
                a = int(args.get("a"))
                b = int(args.get("b"))
            except Exception:
                raise HTTPException(status_code=422, detail={"error": "beta.args.invalid"})
            return {"intent": "beta.reply", "output": str(a + b), "success": True}
        else:
            return {"intent": "beta.reply", "output": f"unknown task: {task_name}", "success": False}

    # Prompt path (validate via SFT beta@v1)
    ok, errs = sft_beta.validate(req)
    if not ok:
        raise HTTPException(status_code=422, detail={"error": "odin.sft.invalid", "violations": errs})

    prompt = str(req.get("prompt", ""))
    m = re.search(r"(\d+)\s*\+\s*(\d+)", prompt)
    if m:
        return {"intent": "beta.reply", "output": str(int(m.group(1)) + int(m.group(2))), "success": True}
    return {"intent": "beta.reply", "output": prompt.upper(), "success": True}
