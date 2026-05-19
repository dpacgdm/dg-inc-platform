from __future__ import annotations

import json
import logging
import os
import time
import uuid
from contextlib import contextmanager
from typing import Any, Callable

import psycopg
import redis
from fastapi import Request
from fastapi.responses import JSONResponse
from pythonjsonlogger import jsonlogger


LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
POSTGRES_DSN = os.getenv("POSTGRES_DSN", "postgresql://dg:dg@postgres:5432/dgvideo")
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")


def configure_logging(service_name: str) -> logging.Logger:
    logger = logging.getLogger(service_name)
    logger.setLevel(LOG_LEVEL)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = jsonlogger.JsonFormatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s %(service)s %(request_id)s"
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger


def request_id_from(request: Request) -> str:
    return request.headers.get("x-request-id") or str(uuid.uuid4())


def log_event(logger: logging.Logger, level: str, message: str, service: str, request_id: str, **fields: Any) -> None:
    payload = {"service": service, "request_id": request_id, **fields}
    getattr(logger, level)(message, extra=payload)


async def request_logging_middleware(request: Request, call_next: Callable):
    service = os.getenv("SERVICE_NAME", "unknown-service")
    logger = logging.getLogger(service)
    rid = request_id_from(request)
    start = time.time()
    try:
        response = await call_next(request)
        response.headers["x-request-id"] = rid
        elapsed_ms = round((time.time() - start) * 1000, 2)
        log_event(
            logger,
            "info",
            "request completed",
            service,
            rid,
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            elapsed_ms=elapsed_ms,
        )
        return response
    except Exception as exc:
        elapsed_ms = round((time.time() - start) * 1000, 2)
        log_event(
            logger,
            "exception",
            "request failed",
            service,
            rid,
            method=request.method,
            path=request.url.path,
            elapsed_ms=elapsed_ms,
            error=str(exc),
        )
        return JSONResponse(status_code=500, content={"error": "internal_error", "request_id": rid})


@contextmanager
def db_conn():
    with psycopg.connect(POSTGRES_DSN) as conn:
        yield conn


def redis_client() -> redis.Redis:
    return redis.Redis.from_url(REDIS_URL, decode_responses=True)


def dependency_status() -> dict[str, Any]:
    status: dict[str, Any] = {"postgres": "unknown", "redis": "unknown"}
    try:
        with db_conn() as conn:
            conn.execute("select 1")
        status["postgres"] = "ok"
    except Exception as exc:
        status["postgres"] = f"failed: {exc}"
    try:
        redis_client().ping()
        status["redis"] = "ok"
    except Exception as exc:
        status["redis"] = f"failed: {exc}"
    return status


def enqueue_processing_job(video_id: str) -> None:
    redis_client().rpush("video-processing-jobs", json.dumps({"video_id": video_id}))


def init_schema() -> None:
    with db_conn() as conn:
        conn.execute(
            """
            create table if not exists users (
                id text primary key,
                handle text not null unique,
                created_at timestamptz not null default now()
            )
            """
        )
        conn.execute(
            """
            create table if not exists videos (
                id text primary key,
                creator_id text not null,
                title text not null,
                description text not null default '',
                status text not null default 'registered',
                object_key text,
                duration_seconds integer,
                created_at timestamptz not null default now(),
                updated_at timestamptz not null default now()
            )
            """
        )
        conn.commit()
