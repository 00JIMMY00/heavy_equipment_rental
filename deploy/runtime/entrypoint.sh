#!/bin/bash
set -e
umask 0002
# All containers use the same immutable assets path, including rollback.
if [[ ! -L sites/assets ]]; then
  rm -rf sites/assets
  ln -s /home/frappe/frappe-bench/assets sites/assets
fi
exec "$@"
