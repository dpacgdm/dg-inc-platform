# D&G Video Platform v0

D&G Video Platform v0 is a production-shaped YouTube-like local platform built for SRE practice.

It focuses on the first reliability-critical customer journey:

```text
creator -> upload metadata -> upload complete -> processing queue -> transcoder worker -> feed -> playback metadata
```

## Services

| Service | Port | Purpose |
|---|---:|---|
| identity-service | 8001 | User/creator identity simulation |
| video-metadata-service | 8002 | Source of truth for video metadata and processing status |
| upload-api | 8003 | Upload registration and completion API |
| feed-service | 8004 | Lists processed/playable videos |
| playback-api | 8005 | Returns simulated playback manifest metadata |
| transcoder-worker-sim | none | Consumes Redis jobs and marks videos processed |

## Dependencies

- PostgreSQL: metadata persistence
- Redis: async processing queue

## Why this exists

This is not a frontend clone. It is an SRE lab for video-platform operations:

- health vs readiness
- request IDs
- structured logs
- dependency failures
- queue backlog
- worker failure
- metadata consistency
- playback reliability
- incident drills
