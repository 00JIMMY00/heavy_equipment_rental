#!/bin/bash
set -e
exec env/bin/gunicorn --chdir=sites --bind=0.0.0.0:8000 \
  --threads="${GUNICORN_THREADS:-4}" --workers="${GUNICORN_WORKERS:-2}" \
  --worker-class=gthread --worker-tmp-dir=/dev/shm --timeout=120 --preload frappe.app:application
