#!/bin/bash
set -Eeuo pipefail
# Bind mounts start empty; preserve existing configuration on updates/restores.
test -f sites/common_site_config.json || printf '{}\n' > sites/common_site_config.json
ls -1 apps > sites/apps.txt
bench set-config -g db_host db
bench set-config -gp db_port 3306
bench set-config -g redis_cache redis://redis-cache:6379
bench set-config -g redis_queue redis://redis-queue:6379
bench set-config -g redis_socketio redis://redis-queue:6379
bench set-config -gp socketio_port 9000
