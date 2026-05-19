from __future__ import annotations

import os
import uuid

from fastapi import FastAPI, Request
from pydantic import BaseModel

from app.common import configure_logging, db_conn, dependency_status, init_schema, request_logging_middleware

SERVICE = "video-metadata-service"
os.environ["SERVICE_NAME"] = SERVICE
logger = configure_logging(SERVICE)
app = FastAPI(title="D&G Video Metadata Service")
app.middleware("http")(request_logging_middleware)


class CreateVideoRequest(BaseModel):
    creator_id: str
    title: str
    description: str = ""


class UpdateVideoStatusRequest(BaseModel):
    status: str
    object_key: str | None = None
    duration_seconds: int | None = None


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


@app.post("/videos")
def create_video(payload: CreateVideoRequest, request: Request) -> dict[str, str]:
    video_id = f"vid_{uuid.uuid4().hex[:12]}"
    with db_conn() as conn:
        conn.execute(
            "insert into videos (id, creator_id, title, description, status) values (%s, %s, %s, %s, %s)",
            (video_id, payload.creator_id, payload.title, payload.description, "registered"),
        )
        conn.commit()
    return {"id": video_id, "status": "registered"}


@app.get("/videos/{video_id}")
def get_video(video_id: str) -> dict[str, object]:
    with db_conn() as conn:
        row = conn.execute(
            "select id, creator_id, title, description, status, object_key, duration_seconds from videos where id = %s",
            (video_id,),
        ).fetchone()
    if not row:
        return {"error": "not_found"}
    return {
        "id": row[0],
        "creator_id": row[1],
        "title": row[2],
        "description": row[3],
        "status": row[4],
        "object_key": row[5],
        "duration_seconds": row[6],
    }


@app.patch("/videos/{video_id}/status")
def update_video_status(video_id: str, payload: UpdateVideoStatusRequest) -> dict[str, object]:
    with db_conn() as conn:
        row = conn.execute(
            """
            update videos
               set status = %s,
                   object_key = coalesce(%s, object_key),
                   duration_seconds = coalesce(%s, duration_seconds),
                   updated_at = now()
             where id = %s
         returning id, status, object_key, duration_seconds
            """,
            (payload.status, payload.object_key, payload.duration_seconds, video_id),
        ).fetchone()
        conn.commit()
    if not row:
        return {"error": "not_found"}
    return {"id": row[0], "status": row[1], "object_key": row[2], "duration_seconds": row[3]}


@app.get("/videos")
def list_videos(status: str | None = None) -> list[dict[str, object]]:
    query = "select id, creator_id, title, description, status, object_key, duration_seconds from videos"
    params: tuple[object, ...] = ()
    if status:
        query += " where status = %s"
        params = (status,)
    query += " order by created_at desc limit 50"
    with db_conn() as conn:
        rows = conn.execute(query, params).fetchall()
    return [
        {
            "id": row[0],
            "creator_id": row[1],
            "title": row[2],
            "description": row[3],
            "status": row[4],
            "object_key": row[5],
            "duration_seconds": row[6],
        }
        for row in rows
    ]
