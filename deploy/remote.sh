#!/usr/bin/env bash
set -Eeuo pipefail
: "${SSH_HOST:?}" "${SSH_USER:?}" "${SSH_KEY:?}" "${SSH_KNOWN_HOSTS:?}" "${IMAGE_REF:?}" "${GHCR_USER:?}" "${GHCR_TOKEN:?}"
[[ $IMAGE_REF =~ ^ghcr\.io/00jimmy00/heavy_equipment_rental@sha256:[a-f0-9]{64}$ ]]
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
chmod 700 "$work"
printf '%s\n' "$SSH_KEY" > "$work/key"
printf '%s\n' "$SSH_KNOWN_HOSTS" > "$work/known_hosts"
chmod 600 "$work/key" "$work/known_hosts"
mkdir "$work/deploy"
cp deploy/compose.yaml deploy/Caddyfile deploy/release.py "$work/deploy/"
printf '%s' "$GHCR_USER" > "$work/registry-user"
printf '%s' "$GHCR_TOKEN" > "$work/registry-token"
tar -C "$work" -czf - deploy registry-user registry-token | \
  ssh -i "$work/key" -o BatchMode=yes -o StrictHostKeyChecking=yes \
  -o UserKnownHostsFile="$work/known_hosts" "$SSH_USER@$SSH_HOST" "$IMAGE_REF"
