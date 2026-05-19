from __future__ import annotations

import os
import uuid

from fastapi import FastAPI, Request
from pydantic import BaseModel

from app.common import configure_logging, db_conn, dependency_status, init_schema, request_logging_middleware

SERVICE = "identity-service"
os.environ["SERVICE_NAME"] = SERVICE
logger = configure_logging(SERVICE)
app = FastAPI(title="D&G Identity Service")
app.middleware("http")(request_logging_middleware)


class CreateUserRequest(BaseModel):
    handle: str


@app.on_event("startup")
def startup() -> None:
    init_schema()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": SERVICE}


@app.get("/ready")
def ready() -> dict[str, object]:
    deps = dependency_status()
    ready_state = deps["postgres"] == "ok"
    return {"ready": ready_state, "dependencies": deps}


@app.post("/users")
def create_user(payload: CreateUserRequest, request: Request) -> dict[str, str]:
    user_id = f"usr_{uuid.uuid4().hex[:12]}"
    with db_conn() as conn:
        conn.execute("insert into users (id, handle) values (%s, %s)", (user_id, payload.handle))
        conn.commit()
    return {"id": user_id, "handle": payload.handle}


@app.get("/users/{user_id}")
def get_user(user_id: str) -> dict[str, str]:
    with db_conn() as conn:
        row = conn.execute("select id, handle from users where id = %s", (user_id,)).fetchone()
    if not row:
        return {"error": "not_found"}
    return {"id": row[0], "handle": row[1]}
