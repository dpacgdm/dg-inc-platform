from __future__ import annotations

import json
import os
import time

import httpx

from app.common import configure_logging, init_schema, redis_client

SERVICE = "transcoder-worker-sim"
os.environ["SERVICE_NAME"] = SERVICE
METADATA_URL = os.getenv("METADATA_URL", "http://video-metadata-service:8000")
PROCESSING_SECONDS = float(os.getenv("PROCESSING_SECONDS", "2"))
logger = configure_logging(SERVICE)


def process_video(video_id: str) -> None:
    logger.info("processing started", extra={"service": SERVICE, "request_id": video_id, "video_id": video_id})
    httpx.patch(f"{METADATA_URL}/videos/{video_id}/status", json={"status": "processing"}, timeout=5.0).raise_for_status()
    time.sleep(PROCESSING_SECONDS)
    httpx.patch(
        f"{METADATA_URL}/videos/{video_id}/status",
        json={"status": "processed", "duration_seconds": 180},
        timeout=5.0,
    ).raise_for_status()
    logger.info("processing completed", extra={"service": SERVICE, "request_id": video_id, "video_id": video_id})


def main() -> None:
    init_schema()
    r = redis_client()
    logger.info("worker started", extra={"service": SERVICE, "request_id": "startup"})
    while True:
        item = r.blpop("video-processing-jobs", timeout=5)
        if not item:
            continue
        _, raw = item
        try:
            payload = json.loads(raw)
            process_video(payload["video_id"])
        except Exception as exc:
            logger.exception("processing failed", extra={"service": SERVICE, "request_id": "worker", "error": str(exc), "raw_job": raw})
            time.sleep(2)


if __name__ == "__main__":
    main()
