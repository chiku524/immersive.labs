#!/usr/bin/env bash
# Lightweight concurrent GET smoke against the Studio API (Worker or origin).
# Usage:
#   STUDIO_URL=https://api.immersivelabs.space STUDIO_KEY=sk_... ./scripts/studio-load-smoke.sh
#   STUDIO_CONCURRENCY=8 STUDIO_ROUNDS=30 ./scripts/studio-load-smoke.sh
set -euo pipefail
STUDIO_URL="${STUDIO_URL:-http://127.0.0.1:8787}"
STUDIO_KEY="${STUDIO_KEY:-}"
CONCURRENCY="${STUDIO_CONCURRENCY:-4}"
ROUNDS="${STUDIO_ROUNDS:-20}"

hdr=()
if [[ -n "$STUDIO_KEY" ]]; then
  hdr=( -H "Authorization: Bearer ${STUDIO_KEY}" )
fi

worker() {
  local i="$1"
  local ok=0 fail=0
  local r
  for ((j=0; j<ROUNDS; j++)); do
    if r=$(curl -fsS "${hdr[@]}" "${STUDIO_URL}/api/studio/health" -o /dev/null -w "%{http_code}"); then
      if [[ "$r" == "200" ]]; then ok=$((ok+1)); else fail=$((fail+1)); fi
    else
      fail=$((fail+1))
    fi
  done
  echo "worker $i: ok=$ok fail=$fail"
}

pids=()
for ((i=0; i<CONCURRENCY; i++)); do
  worker "$i" &
  pids+=( "$!" )
done
for pid in "${pids[@]}"; do
  wait "$pid"
done
echo "Done (concurrency=$CONCURRENCY rounds=$ROUNDS url=$STUDIO_URL)"
