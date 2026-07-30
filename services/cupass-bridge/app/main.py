# SPDX-License-Identifier: Apache-2.0
from __future__ import annotations

import asyncio
import json
import secrets
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field

from .config import settings
from .store import BridgeStore

app = FastAPI(title="Cofer One IA - Cofer U Pass Bridge", version="0.4.0")
store = BridgeStore(settings)


async def auth(authorization: str | None = Header(default=None)) -> None:
    if not settings.api_key:
        raise HTTPException(status_code=503, detail="CUPASS_BRIDGE_API_KEY is not configured")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Bearer token required")
    if not secrets.compare_digest(authorization[7:].strip(), settings.api_key):
        raise HTTPException(status_code=401, detail="invalid bridge token")


class WorkerRegister(BaseModel):
    model_config = ConfigDict(extra="forbid")
    worker_id: str = Field(min_length=1, max_length=160)
    profiles: list[dict[str, Any]]


class JobComplete(BaseModel):
    model_config = ConfigDict(extra="forbid")
    response: dict[str, Any]


class JobFail(BaseModel):
    model_config = ConfigDict(extra="forbid")
    error: str


def _reject_tools(body: dict[str, Any]) -> None:
    if body.get("tools"):
        raise HTTPException(status_code=400, detail="Cofer U Pass web models do not support tools/function calling")
    if body.get("tool_choice") not in {None, "none"}:
        raise HTTPException(status_code=400, detail="Cofer U Pass web models do not support tool_choice")


def _response_text(response: dict[str, Any]) -> str:
    if isinstance(response.get("output_text"), str):
        return response["output_text"]
    try:
        return response["output"][0]["content"][0]["text"]
    except (KeyError, IndexError, TypeError):
        return ""


def _reasoning_effort(body: dict[str, Any]) -> str | None:
    reasoning = body.get("reasoning")
    if reasoning is None:
        return None
    if not isinstance(reasoning, dict):
        raise HTTPException(status_code=400, detail="reasoning must be an object")
    effort = reasoning.get("effort")
    if effort is None:
        return None
    if not isinstance(effort, str) or not effort.strip():
        raise HTTPException(status_code=400, detail="reasoning.effort must be a non-empty string")
    return effort.strip().lower()


async def _resolve_route(body: dict[str, Any]) -> dict[str, Any]:
    model = str(body.get("model") or "").strip()
    if not model:
        raise HTTPException(status_code=400, detail="model is required")
    try:
        return await asyncio.to_thread(store.resolve_model, model, _reasoning_effort(body))
    except KeyError as exc:
        raise HTTPException(status_code=503, detail=f"no active Cofer U Pass route for model: {model}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


async def _wait_job(job_id: str) -> dict[str, Any]:
    deadline = time.monotonic() + settings.request_timeout_seconds
    while time.monotonic() < deadline:
        job = await asyncio.to_thread(store.get_job, job_id)
        if job["status"] == "completed":
            return job["response"]
        if job["status"] == "failed":
            raise HTTPException(status_code=502, detail=job["error"] or "Cofer U Pass worker failed")
        await asyncio.sleep(0.25)
    raise HTTPException(status_code=504, detail="timed out waiting for a Cofer U Pass worker")


@app.get("/")
async def root(_: None = Depends(auth)) -> dict[str, Any]:
    return {"name": "cofer-u-pass-bridge", "version": app.version, "mode": "dynamic-model-text-file-exchange"}


@app.get("/health")
async def health(_: None = Depends(auth)) -> dict[str, Any]:
    profiles = await asyncio.to_thread(store.active_profiles)
    models = await asyncio.to_thread(store.list_models)
    return {
        "status": "ok",
        "workers_profiles": profiles,
        "models": models,
        "jobs": await asyncio.to_thread(store.stats),
    }


@app.get("/v1/models")
async def models(_: None = Depends(auth)) -> dict[str, Any]:
    return {"object": "list", "data": await asyncio.to_thread(store.list_models)}


@app.get("/v1/models/{model:path}/capabilities")
async def model_capabilities(model: str, _: None = Depends(auth)) -> dict[str, Any]:
    try:
        route = await asyncio.to_thread(store.resolve_model, model, None)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"unknown Cofer U Pass model: {model}") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    model_data = route.get("model") or {}
    capabilities = dict(route.get("capabilities") or {})
    capabilities["reasoning_efforts"] = list(model_data.get("reasoning_efforts") or [])
    capabilities["tools"] = False
    capabilities["function_calling"] = False
    return {
        "model": model,
        "provider": route.get("provider"),
        "profile_id": route.get("profile_id"),
        "display_name": model_data.get("display_name") or model,
        "capabilities": capabilities,
        "exchange_protocol": "cofer-u-pass.exchange/1",
    }


@app.post("/v1/files")
async def upload_file(
    file: UploadFile = File(...), purpose: str = Form(default="user_data"), _: None = Depends(auth)
):
    try:
        return await asyncio.to_thread(
            store.put_file,
            file.file,
            filename=file.filename or "upload.bin",
            purpose=purpose,
            mime_type=file.content_type,
        )
    except ValueError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    finally:
        await file.close()


@app.get("/v1/files/{file_id}")
async def file_metadata(file_id: str, _: None = Depends(auth)):
    try:
        return await asyncio.to_thread(store.get_file, file_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="file not found") from exc


@app.get("/v1/files/{file_id}/content")
async def file_content(file_id: str, _: None = Depends(auth)):
    try:
        meta = await asyncio.to_thread(store.get_file, file_id)
        path = await asyncio.to_thread(store.file_path, file_id)
        return FileResponse(path, media_type=meta.get("mime_type") or "application/octet-stream", filename=meta["filename"])
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="file not found") from exc


@app.delete("/v1/files/{file_id}")
async def delete_file(file_id: str, _: None = Depends(auth)):
    try:
        await asyncio.to_thread(store.delete_file, file_id)
        return {"id": file_id, "object": "file", "deleted": True}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="file not found") from exc


async def _buffered_response_stream(response: dict[str, Any]) -> AsyncIterator[str]:
    text = _response_text(response)
    yield "data: " + json.dumps({"type": "response.created", "response": {"id": response.get("id"), "status": "in_progress"}}) + "\n\n"
    if text:
        yield "data: " + json.dumps({"type": "response.output_text.delta", "response_id": response.get("id"), "delta": text}, ensure_ascii=False) + "\n\n"
    yield "data: " + json.dumps({"type": "response.completed", "response": response}, ensure_ascii=False) + "\n\n"
    yield "data: [DONE]\n\n"


@app.post("/v1/responses", response_model=None)
async def responses(request: Request, _: None = Depends(auth)):
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(status_code=400, detail="JSON object expected")
    _reject_tools(body)
    stream = bool(body.get("stream", False))
    route = await _resolve_route(body)
    job_id = await asyncio.to_thread(store.create_job, body, profile_id=route["profile_id"])
    response = await _wait_job(job_id)
    if stream:
        return StreamingResponse(_buffered_response_stream(response), media_type="text/event-stream")
    return JSONResponse(response)


def _chat_to_responses(body: dict[str, Any]) -> dict[str, Any]:
    _reject_tools(body)
    messages = body.get("messages") or []
    if not isinstance(messages, list):
        raise HTTPException(status_code=400, detail="messages must be an array")
    items = []
    for message in messages:
        if not isinstance(message, dict):
            raise HTTPException(status_code=400, detail="messages must contain objects")
        role = message.get("role") or "user"
        content = message.get("content") or ""
        if not isinstance(content, str):
            raise HTTPException(status_code=400, detail="Cofer U Pass chat/completions currently supports text messages only")
        items.append({"type": "message", "role": role, "content": [{"type": "input_text", "text": content}]})
    result: dict[str, Any] = {
        "model": body.get("model"),
        "input": items,
        "stream": False,
        "metadata": body.get("metadata") or {},
        "client_request_id": body.get("client_request_id"),
    }
    effort = body.get("reasoning_effort")
    if effort is not None:
        result["reasoning"] = {"effort": effort}
    return result


def _responses_to_chat(body: dict[str, Any], original: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": "chatcmpl-" + uuid.uuid4().hex,
        "object": "chat.completion",
        "created": int(time.time()),
        "model": original.get("model"),
        "choices": [{"index": 0, "message": {"role": "assistant", "content": _response_text(body)}, "finish_reason": "stop"}],
        "usage": body.get("usage") or {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
    }


@app.post("/v1/chat/completions", response_model=None)
async def chat_completions(request: Request, _: None = Depends(auth)):
    original = await request.json()
    if not isinstance(original, dict):
        raise HTTPException(status_code=400, detail="JSON object expected")
    converted = _chat_to_responses(original)
    route = await _resolve_route(converted)
    job_id = await asyncio.to_thread(store.create_job, converted, profile_id=route["profile_id"])
    response = await _wait_job(job_id)
    final = _responses_to_chat(response, original)
    if not original.get("stream"):
        return JSONResponse(final)

    async def stream() -> AsyncIterator[str]:
        text = final["choices"][0]["message"]["content"]
        chunk_id = final["id"]
        yield "data: " + json.dumps({
            "id": chunk_id,
            "object": "chat.completion.chunk",
            "created": final["created"],
            "model": final["model"],
            "choices": [{"index": 0, "delta": {"role": "assistant", "content": text}, "finish_reason": None}],
        }, ensure_ascii=False) + "\n\n"
        yield "data: " + json.dumps({
            "id": chunk_id,
            "object": "chat.completion.chunk",
            "created": final["created"],
            "model": final["model"],
            "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
        }) + "\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.post("/internal/v1/workers/register")
async def register_worker(body: WorkerRegister, _: None = Depends(auth)):
    await asyncio.to_thread(store.register_worker, body.worker_id, body.profiles)
    return {"status": "registered", "worker_id": body.worker_id}


@app.post("/internal/v1/workers/{worker_id}/heartbeat")
async def heartbeat(worker_id: str, _: None = Depends(auth)):
    try:
        await asyncio.to_thread(store.heartbeat, worker_id)
        return {"status": "ok"}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="worker not registered") from exc


@app.get("/internal/v1/jobs/next", response_model=None)
async def next_job(worker_id: str = Query(...), profiles: str = Query(...), _: None = Depends(auth)):
    profile_list = [p.strip() for p in profiles.split(",") if p.strip()]
    deadline = time.monotonic() + settings.worker_poll_seconds
    while time.monotonic() < deadline:
        try:
            await asyncio.to_thread(store.heartbeat, worker_id)
        except KeyError as exc:
            raise HTTPException(status_code=409, detail="worker must register before polling") from exc
        job = await asyncio.to_thread(store.lease_job, worker_id, profile_list)
        if job:
            return job
        await asyncio.sleep(0.5)
    return JSONResponse(status_code=204, content=None)


@app.get("/internal/v1/files/{file_id}/content")
async def internal_file_content(file_id: str, _: None = Depends(auth)):
    try:
        meta = await asyncio.to_thread(store.get_file, file_id)
        path = await asyncio.to_thread(store.file_path, file_id)
        return FileResponse(
            path,
            media_type=meta.get("mime_type") or "application/octet-stream",
            headers={"X-Cofer-Filename": meta["filename"]},
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="file not found") from exc


@app.post("/internal/v1/jobs/{job_id}/artifacts")
async def upload_artifact(
    job_id: str,
    request: Request,
    filename: str = Query(...),
    _: None = Depends(auth),
):
    try:
        job = await asyncio.to_thread(store.get_job, job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="job not found") from exc
    if job["status"] != "leased":
        raise HTTPException(status_code=409, detail="job is not leased")
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=f"artifact-{job_id}-",
            suffix=".upload",
            dir=store.root,
            delete=False,
        ) as temp:
            temp_path = Path(temp.name)
            size = 0
            async for chunk in request.stream():
                if not chunk:
                    continue
                size += len(chunk)
                if size > settings.max_file_bytes:
                    raise ValueError("file exceeds CUPASS_BRIDGE_MAX_FILE_BYTES")
                temp.write(chunk)
            temp.flush()
        meta = await asyncio.to_thread(
            store.put_path,
            temp_path,
            filename=filename,
            purpose="cofer_u_pass_output",
            mime_type=request.headers.get("content-type"),
            job_id=job_id,
        )
        temp_path = None
        return meta
    except ValueError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    finally:
        if temp_path is not None:
            temp_path.unlink(missing_ok=True)


@app.post("/internal/v1/jobs/{job_id}/complete")
async def complete(job_id: str, body: JobComplete, _: None = Depends(auth)):
    try:
        await asyncio.to_thread(store.complete_job, job_id, body.response)
        return {"status": "completed"}
    except KeyError as exc:
        raise HTTPException(status_code=409, detail="job is not leased or does not exist") from exc


@app.post("/internal/v1/jobs/{job_id}/fail")
async def fail(job_id: str, body: JobFail, _: None = Depends(auth)):
    try:
        await asyncio.to_thread(store.fail_job, job_id, body.error)
        return {"status": "failed"}
    except KeyError as exc:
        raise HTTPException(status_code=409, detail="job is not leased or does not exist") from exc
