from __future__ import annotations

import os

import httpx
from fastapi import FastAPI, Request

from app.common import configure_logging, request_logging_middleware

SERVICE = "playback-api"
os.environ["SERVICE_NAME"] = SERVICE
METADATA_URL = os.getenv("METADATA_URL", "http://video-metadata-service:8000")
logger = configure_logging(SERVICE)
app = FastAPI(title="D&G Playback API")
app.middleware("http")(request_logging_middleware)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": SERVICE}


@app.get("/ready")
def ready() -> dict[str, object]:
    metadata_ok = False
    metadata_status = "failed"
    try:
        response = httpx.get(f"{METADATA_URL}/ready", timeout=2.0)
        metadata_ok = response.status_code == 200 and bool(response.json().get("ready"))
        metadata_status = "ok" if metadata_ok else f"not_ready: {response.text[:200]}"
    except Exception as exc:
        metadata_status = f"failed: {exc}"

    return {
        "ready": metadata_ok,
        "dependencies": {"video-metadata-service": metadata_status},
    }


@app.get("/playback/{video_id}")
def playback(video_id: str, request: Request) -> dict[str, object]:
    try:
        response = httpx.get(
            f"{METADATA_URL}/videos/{video_id}",
            headers={"x-request-id": request.headers.get("x-request-id", "")},
            timeout=3.0,
        )
        response.raise_for_status()
    except Exception as exc:
        return {"error": "metadata_dependency_failed", "video_id": video_id, "detail": str(exc)}

    video = response.json()
    if video.get("error") == "not_found":
        return {"error": "not_found", "video_id": video_id}

    if video.get("status") != "processed":
        return {"error": "not_playable", "video_id": video_id, "status": video.get("status")}

    return {
        "video_id": video["id"],
        "title": video["title"],
        "status": video["status"],
        "manifest_url": f"local-cdn://manifests/{video['id']}.m3u8",
        "renditions": ["360p", "720p", "1080p"],
        "object_key": video.get("object_key"),
        "duration_seconds": video.get("duration_seconds"),
        "metadata_source": "video-metadata-service",
    }
