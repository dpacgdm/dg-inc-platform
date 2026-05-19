# D&G Video Platform Local Runbook

## Purpose

Operate D&G Video Platform v0 locally using Docker Compose.

This environment simulates a YouTube-like upload-processing-playback platform for SRE practice.

## Start platform

```bash
cd ~/dg-inc-platform
git pull
docker compose -f infra/local/docker-compose.yml up --build
```

In another terminal:

```bash
bash scripts/smoke/video-platform-smoke.sh
```

## Service ports

| Service | URL |
|---|---|
| identity-service | http://localhost:8001 |
| video-metadata-service | http://localhost:8002 |
| upload-api | http://localhost:8003 |
| feed-service | http://localhost:8004 |
| playback-api | http://localhost:8005 |
| postgres | localhost:5432 |
| redis | localhost:6379 |

## Health checks

```bash
curl -s http://localhost:8001/ready | jq
curl -s http://localhost:8002/ready | jq
curl -s http://localhost:8003/ready | jq
curl -s http://localhost:8004/ready | jq
curl -s http://localhost:8005/ready | jq
```

## Smoke test

```bash
bash scripts/smoke/video-platform-smoke.sh
```

Expected result:

```text
[smoke] D&G Video Platform v0 smoke test passed
```

## Logs

All services emit JSON-ish structured logs with `service` and `request_id`.

```bash
docker compose -f infra/local/docker-compose.yml logs -f upload-api
docker compose -f infra/local/docker-compose.yml logs -f transcoder-worker-sim
docker compose -f infra/local/docker-compose.yml logs -f playback-api
```

## Failure scenario 1: worker down

Stop the worker:

```bash
docker compose -f infra/local/docker-compose.yml stop transcoder-worker-sim
```

Run smoke test. Expected behavior:

- upload succeeds
- processing job is queued
- playback remains `not_playable`
- feed does not show the new video

Check Redis queue backlog:

```bash
docker compose -f infra/local/docker-compose.yml exec redis redis-cli llen video-processing-jobs
```

Recover:

```bash
docker compose -f infra/local/docker-compose.yml start transcoder-worker-sim
```

## Failure scenario 2: Redis down

```bash
docker compose -f infra/local/docker-compose.yml stop redis
curl -s http://localhost:8003/ready | jq
```

Expected:

- upload-api readiness should show Redis failed
- upload completion should fail because job enqueue cannot happen

Recover:

```bash
docker compose -f infra/local/docker-compose.yml start redis
```

## Failure scenario 3: Postgres down

```bash
docker compose -f infra/local/docker-compose.yml stop postgres
curl -s http://localhost:8002/ready | jq
curl -s http://localhost:8005/ready | jq
```

Expected:

- metadata and playback readiness fail
- customer journey breaks at metadata lookup/persistence

Recover:

```bash
docker compose -f infra/local/docker-compose.yml start postgres
```

## First 10-minute incident triage

1. Confirm customer journey failure using smoke test.
2. Check `/ready` for all public services.
3. Check worker logs and queue backlog.
4. Check Postgres and Redis container health.
5. Identify whether failure is synchronous path or async processing path.
6. Mitigate: restart dependency, restart worker, or stop bad deploy.
7. Record incident if customer journey is affected.

## SLO draft

Playback availability:

```text
99.9% of playback metadata requests for processed videos should return a playable manifest response within 300 ms over a 30-day window.
```

Video processing latency:

```text
99% of uploaded videos should reach processed status within 5 minutes in v0 local simulation.
```
