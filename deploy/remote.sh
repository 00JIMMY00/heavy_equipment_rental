#!/usr/bin/env bash
set -Eeuo pipefail

for name in SSH_HOST SSH_USER SSH_KEY SSH_KNOWN_HOSTS DEPLOY_DIR IMAGE_REF GHCR_USER GHCR_TOKEN; do
  [[ -n "${!name:-}" ]] || { echo "Missing $name" >&2; exit 2; }
done
[[ "$SSH_HOST" =~ ^[a-zA-Z0-9.-]+$ && "$SSH_USER" =~ ^[a-zA-Z0-9_-]+$ \
  && "$DEPLOY_DIR" =~ ^/[a-zA-Z0-9._/-]+$ && "$GHCR_USER" =~ ^[a-zA-Z0-9_-]+$ \
  && "$IMAGE_REF" =~ ^ghcr\.io/[a-z0-9._/-]+@sha256:[a-f0-9]{64}$ ]] || {
  echo "Invalid SSH or deployment setting" >&2
  exit 2
}

key_file="$(mktemp)"
hosts_file="$(mktemp)"
trap 'rm -f "$key_file" "$hosts_file"' EXIT
chmod 600 "$key_file" "$hosts_file"
printf '%s\n' "$SSH_KEY" > "$key_file"
printf '%s\n' "$SSH_KNOWN_HOSTS" > "$hosts_file"
ssh_opts=(-i "$key_file" -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile="$hosts_file")
target="$SSH_USER@$SSH_HOST"

ssh "${ssh_opts[@]}" "$target" "mkdir -p '$DEPLOY_DIR'"
scp "${ssh_opts[@]}" deploy/rollout.sh deploy/compose.yaml \
  deploy/clients_runtime.py deploy/clients.json "$target:$DEPLOY_DIR/"
printf '%s' "$GHCR_TOKEN" | ssh "${ssh_opts[@]}" "$target" \
  "set -e; export DOCKER_CONFIG=\"\$(mktemp -d)\"; trap 'rm -rf \"\$DOCKER_CONFIG\"' EXIT; docker login ghcr.io --username '$GHCR_USER' --password-stdin; cd '$DEPLOY_DIR'; bash rollout.sh '$IMAGE_REF'"
