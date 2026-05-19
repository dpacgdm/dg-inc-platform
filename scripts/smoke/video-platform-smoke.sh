#!/usr/bin/env bash
set -euo pipefail

BASE_IDENTITY=${BASE_IDENTITY:-http://localhost:8001}
BASE_UPLOAD=${BASE_UPLOAD:-http://localhost:8003}
BASE_FEED=${BASE_FEED:-http://localhost:8004}
BASE_PLAYBACK=${BASE_PLAYBACK:-http://localhost:8005}
REQUEST_ID=${REQUEST_ID:-dg-smoke-$(date +%s)}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || { echo "missing required command: $1" >&2; exit 1; }
}

require_cmd curl
require_cmd python3

echo "[smoke] request_id=$REQUEST_ID"

echo "[smoke] checking service readiness"
for url in "$BASE_IDENTITY/ready" "$BASE_UPLOAD/ready" "$BASE_FEED/ready" "$BASE_PLAYBACK/ready"; do
  curl -fsS -H "x-request-id: $REQUEST_ID" "$url" >/dev/null
  echo "[smoke] ready: $url"
done

echo "[smoke] creating creator"
USER_RESPONSE=$(curl -fsS -X POST "$BASE_IDENTITY/users" \
  -H 'content-type: application/json' \
  -H "x-request-id: $REQUEST_ID" \
  -d '{"handle":"dg_creator_'"$(date +%s)"'"}')
USER_ID=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["id"])' <<< "$USER_RESPONSE")
echo "[smoke] user_id=$USER_ID"

echo "[smoke] registering upload"
UPLOAD_RESPONSE=$(curl -fsS -X POST "$BASE_UPLOAD/uploads" \
  -H 'content-type: application/json' \
  -H "x-request-id: $REQUEST_ID" \
  -d '{"creator_id":"'"$USER_ID"'","title":"D&G Smoke Test Video","description":"Synthetic video upload path"}')
VIDEO_ID=$(python3 -c 'import json,sys; print(json.load(sys.stdin)["video_id"])' <<< "$UPLOAD_RESPONSE")
echo "[smoke] video_id=$VIDEO_ID"

echo "[smoke] completing upload and enqueueing processing job"
curl -fsS -X POST "$BASE_UPLOAD/uploads/$VIDEO_ID/complete" \
  -H 'content-type: application/json' \
  -H "x-request-id: $REQUEST_ID" \
  -d '{"object_key":"raw/'"$VIDEO_ID"'.mp4"}' >/dev/null

echo "[smoke] waiting for worker to mark video processed"
for attempt in {1..20}; do
  PLAYBACK_RESPONSE=$(curl -fsS -H "x-request-id: $REQUEST_ID" "$BASE_PLAYBACK/playback/$VIDEO_ID")
  if python3 -c 'import json,sys; data=json.load(sys.stdin); sys.exit(0 if data.get("status") == "processed" else 1)' <<< "$PLAYBACK_RESPONSE"; then
    echo "[smoke] playback ready"
    echo "$PLAYBACK_RESPONSE"
    break
  fi
  echo "[smoke] not playable yet attempt=$attempt"
  sleep 1
  if [[ "$attempt" == "20" ]]; then
    echo "[smoke] video did not become playable" >&2
    echo "$PLAYBACK_RESPONSE" >&2
    exit 1
  fi
done

echo "[smoke] checking feed contains processed items"
FEED_RESPONSE=$(curl -fsS -H "x-request-id: $REQUEST_ID" "$BASE_FEED/feed")
python3 -c 'import json,sys; data=json.load(sys.stdin); assert len(data.get("items", [])) >= 1; print("[smoke] feed_items=", len(data["items"]))' <<< "$FEED_RESPONSE"

echo "[smoke] D&G Video Platform v0 smoke test passed"
