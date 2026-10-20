#!/usr/bin/env bash
set -Eeuo pipefail

cd "$(dirname "$0")"
if [[ $# -ne 1 || ! "$1" =~ ^ghcr\.io/[a-z0-9._/-]+@sha256:[a-f0-9]{64}$ ]]; then
  echo "Usage: rollout.sh ghcr.io/owner/image@sha256:<64 hexadecimal characters>" >&2
  exit 2
fi
target_ref="$1"
[[ -f .env && -f deploy.conf && -f clients.json ]] || {
  echo "Missing .env, deploy.conf, or clients.json" >&2
  exit 2
}
source ./deploy.conf
: "${HEALTH_TIMEOUT:=180}"
mapfile -t sites < <(python3 clients_runtime.py sites)
[[ ${#sites[@]} -gt 0 ]] || { echo "No sites in clients.json" >&2; exit 2; }

exec 9>.rollout.lock
flock -n 9 || { echo "Another rollout is running" >&2; exit 1; }

compose() {
  docker compose -f compose.yaml "$@"
}

old_container="$(compose ps -q backend 2>/dev/null || true)"
old_ref=""
if [[ -n "$old_container" ]]; then
  old_ref="$(docker inspect --format '{{.Config.Image}}' "$old_container")"
  docker image inspect "$old_ref" >/dev/null
fi

# Pulling cannot affect running containers. Repeat validation on a same-image rerun.
export APP_IMAGE="$target_ref"
echo "Ensuring all stack images are present, including $target_ref"
compose pull --policy missing || exit 1

if [[ -n "$old_ref" ]]; then
  echo "Backing up ${#sites[@]} sites before migration"
  for site in "${sites[@]}"; do
    compose exec -T backend bench --site "$site" backup --with-files --compress || exit 1
  done
fi

check_sites() {
  local site installed
  for site in "${sites[@]}"; do
    installed="$(compose exec -T backend bench --site "$site" list-apps -f json)" || return 1
    printf '%s' "$installed" | python3 clients_runtime.py check "$site" || return 1
    compose exec -T backend bench --site "$site" migrate || return 1
  done
}

healthy() {
  local service cid state site
  for service in backend frontend websocket queue-short queue-long scheduler; do
    cid="$(compose ps -q "$service")"
    [[ -n "$cid" ]] || return 1
    state="$(docker inspect --format '{{.State.Status}}' "$cid")"
    [[ "$state" == running ]] || return 1
  done
  for site in "${sites[@]}"; do
    curl --silent --show-error --fail --max-time 8 \
      --header "Host: $site" \
      "http://127.0.0.1:8083/api/method/ping" >/dev/null || return 1
  done
}

wait_healthy() {
  local deadline=$((SECONDS + HEALTH_TIMEOUT))
  until healthy; do
    (( SECONDS < deadline )) || return 1
    sleep 5
  done
}

roll_forward() {
  compose up -d --pull never || return 1
  check_sites || return 1
  wait_healthy
}

if ! roll_forward; then
  echo "Release failed; restoring previous application image if available" >&2
  if [[ -n "$old_ref" && "$old_ref" != "$target_ref" ]]; then
    export APP_IMAGE="$old_ref"
    if ! compose up -d --pull never || ! wait_healthy; then
      echo "Rollback also failed; inspect Compose logs and site backups" >&2
    fi
  elif [[ -z "$old_ref" ]]; then
    echo "First deployment has no previous image; the stack remains for site setup" >&2
  fi
  echo "A container rollback does not reverse database migrations" >&2
  exit 1
fi

python3 - "$target_ref" <<'PY'
import os
import pathlib
import sys
import tempfile

path = pathlib.Path(".env")
lines = path.read_text().splitlines()
lines = [line for line in lines if line.split("=", 1)[0] != "APP_IMAGE"]
lines.append(f"APP_IMAGE={sys.argv[1]}")
with tempfile.NamedTemporaryFile(mode="w", dir=".", delete=False) as tmp:
    tmp.write("\n".join(lines) + "\n")
    temp_name = tmp.name
os.chmod(temp_name, path.stat().st_mode & 0o777)
os.replace(temp_name, path)
PY

# Compose replaces prior app containers. Keep exactly two successful image refs.
history=.image-history
mapfile -t prior < <(cat "$history" 2>/dev/null || true)
keep_previous=""
if [[ -n "$old_ref" && "$old_ref" != "$target_ref" ]]; then
  keep_previous="$old_ref"
elif [[ "$old_ref" == "$target_ref" && ${#prior[@]} -gt 1 ]]; then
  keep_previous="${prior[1]}"
fi
printf '%s\n' "$target_ref" > "$history"
if [[ -n "$keep_previous" ]]; then
  printf '%s\n' "$keep_previous" >> "$history"
fi
for ref in "${prior[@]}"; do
  if [[ -n "$ref" && "$ref" != "$target_ref" && "$ref" != "$keep_previous" ]]; then
    docker image rm "$ref" || echo "Could not remove unused image $ref" >&2
  fi
done
echo "Deployment complete: $target_ref"
