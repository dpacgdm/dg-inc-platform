from __future__ import annotations

import os

import httpx
from fastapi import FastAPI, Request
from pydantic import BaseModel

from app.common import configure_logging, dependency_status, enqueue_processing_job, init_schema, request_logging_middleware

SERVICE = "upload-api"
os.environ["SERVICE_NAME"] = SERVICE
METADATA_URL = os.getenv("METADATA_URL", "http://video-metadata-service:8000")
logger = configure_logging(SERVICE)
app = FastAPI(title="D&G Upload API")
app.middleware("http")(request_logging_middleware)


class RegisterUploadRequest(BaseModel):
    creator_id: str
    title: str
    description: str = ""


class CompleteUploadRequest(BaseModel):
    object_key: str


@app.on_event("startup")
def startup() -> None:
    init_schema()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": SERVICE}


@app.get("/ready")
def ready() -> dict[str, object]:
    deps = dependency_status()
    metadata_ok = False
    try:
        response = httpx.get(f"{METADATA_URL}/health", timeout=2.0)
        metadata_ok = response.status_code == 200
    except Exception:
        metadata_ok = False
    return {"ready": deps["postgres"] == "ok" and deps["redis"] == "ok" and metadata_ok, "dependencies": {**deps, "video-metadata-service": "ok" if metadata_ok else "failed"}}


@app.post("/uploads")
def register_upload(payload: RegisterUploadRequest, request: Request) -> dict[str, str]:
    response = httpx.post(
        f"{METADATA_URL}/videos",
        json={"creator_id": payload.creator_id, "title": payload.title, "description": payload.description},
        headers={"x-request-id": request.headers.get("x-request-id", "")},
        timeout=5.0,
    )
    response.raise_for_status()
    video = response.json()
    return {"video_id": video["id"], "upload_url": f"local-object-store://raw/{video['id']}.mp4", "status": video["status"]}


@app.post("/uploads/{video_id}/complete")
def complete_upload(video_id: str, payload: CompleteUploadRequest, request: Request) -> dict[str, str]:
    response = httpx.patch(
        f"{METADATA_URL}/videos/{video_id}/status",
        json={"status": "uploaded", "object_key": payload.object_key},
        headers={"x-request-id": request.headers.get("x-request-id", "")},
        timeout=5.0,
    )
    response.raise_for_status()
    enqueue_processing_job(video_id)
    return {"video_id": video_id, "status": "uploaded", "processing_job": "queued"}
