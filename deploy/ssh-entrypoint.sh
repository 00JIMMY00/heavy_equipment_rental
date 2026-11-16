#!/usr/bin/env bash
# Installed by the administrator at /usr/local/sbin/her-deploy.
# The dedicated authorized_keys entry can invoke only this command.
set -Eeuo pipefail
umask 077
image=${SSH_ORIGINAL_COMMAND:-}
[[ $image =~ ^ghcr\.io/00jimmy00/heavy_equipment_rental@sha256:[a-f0-9]{64}$ ]] || exit 2
work=$(mktemp -d /opt/her/state/incoming.XXXXXX)
trap 'rm -rf "$work"' EXIT
# Reject links/traversal and accept only the five deployment inputs.
python3 -c '
import sys,tarfile,pathlib
root=pathlib.Path(sys.argv[1])
allowed={"deploy/compose.yaml","deploy/Caddyfile","deploy/release.py","registry-user","registry-token"}
seen=set()
with tarfile.open(fileobj=sys.stdin.buffer,mode="r|gz") as archive:
    for member in archive:
        if member.isdir() and member.name == "deploy":
            continue
        if member.name not in allowed or not member.isfile() or member.name in seen or member.size > 1048576:
            raise SystemExit("Invalid deployment archive")
        dest=root / member.name
        dest.parent.mkdir(exist_ok=True)
        dest.write_bytes(archive.extractfile(member).read())
        seen.add(member.name)
if seen != allowed:
    raise SystemExit("Incomplete deployment archive")
' "$work"
export DOCKER_CONFIG="$work/docker-config"
mkdir "$DOCKER_CONFIG"
docker login ghcr.io -u "$(cat "$work/registry-user")" --password-stdin < "$work/registry-token"
python3 "$work/deploy/release.py" "$image" --root /opt/her --incoming "$work/deploy"
# Keep the installed release command for manual rollback drills and operations.
install -m 0700 "$work/deploy/release.py" /opt/her/release.py
