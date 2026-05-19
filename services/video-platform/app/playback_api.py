from __future__ import annotations

import os

from fastapi import FastAPI

from app.common import configure_logging, db_conn, dependency_status, init_schema, request_logging_middleware

SERVICE = "playback-api"
os.environ["SERVICE_NAME"] = SERVICE
logger = configure_logging(SERVICE)
app = FastAPI(title="D&G Playback API")
app.middleware("http")(request_logging_middleware)


@app.on_event("startup")
def startup() -> None:
    init_schema()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": SERVICE}


@app.get("/ready")
def ready() -> dict[str, object]:
    deps = dependency_status()
    return {"ready": deps["postgres"] == "ok", "dependencies": deps}


@app.get("/playback/{video_id}")
def playback(video_id: str) -> dict[str, object]:
    with db_conn() as conn:
        row = conn.execute(
            "select id, title, status, object_key, duration_seconds from videos where id = %s",
            (video_id,),
        ).fetchone()
    if not row:
        return {"error": "not_found"}
    if row[2] != "processed":
        return {"error": "not_playable", "video_id": row[0], "status": row[2]}
    return {
        "video_id": row[0],
        "title": row[1],
        "status": row[2],
        "manifest_url": f"local-cdn://manifests/{row[0]}.m3u8",
        "renditions": ["360p", "720p", "1080p"],
        "object_key": row[3],
        "duration_seconds": row[4],
    }
