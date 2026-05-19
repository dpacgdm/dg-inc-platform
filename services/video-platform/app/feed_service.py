from __future__ import annotations

import os

from fastapi import FastAPI

from app.common import configure_logging, db_conn, dependency_status, init_schema, request_logging_middleware

SERVICE = "feed-service"
os.environ["SERVICE_NAME"] = SERVICE
logger = configure_logging(SERVICE)
app = FastAPI(title="D&G Feed Service")
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


@app.get("/feed")
def feed(limit: int = 20) -> dict[str, object]:
    with db_conn() as conn:
        rows = conn.execute(
            """
            select id, creator_id, title, description, status, object_key, duration_seconds, created_at
              from videos
             where status = 'processed'
             order by updated_at desc
             limit %s
            """,
            (limit,),
        ).fetchall()
    return {
        "items": [
            {
                "video_id": row[0],
                "creator_id": row[1],
                "title": row[2],
                "description": row[3],
                "status": row[4],
                "object_key": row[5],
                "duration_seconds": row[6],
                "created_at": row[7].isoformat() if row[7] else None,
            }
            for row in rows
        ]
    }
