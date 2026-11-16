#!/bin/bash
set -Eeuo pipefail
bench set-config -g db_host db
bench set-config -gp db_port 3306
bench set-config -g redis_cache redis://redis-cache:6379
bench set-config -g redis_queue redis://redis-queue:6379
bench set-config -g redis_socketio redis://redis-queue:6379
bench new-site her_ci --db-root-password ci-root --admin-password ci-admin \
  --mariadb-user-host-login-scope=% --install-app erpnext --install-app arab_erp_theme --install-app heavy_equipment_rental
bench --site her_ci migrate
bench --site her_ci execute runpy.run_path --args '["apps/heavy_equipment_rental/deploy/ci_setup.py"]' >/dev/null
bench --site her_ci set-config allow_tests true
for module in \
  heavy_equipment_rental.heavy_equipment_rental.doctype.rental_contract.test_rental_workflow \
  heavy_equipment_rental.test_maintenance_lifecycle \
  heavy_equipment_rental.test_maintenance_posting \
  heavy_equipment_rental.test_partner_settlements; do
  bench --site her_ci run-tests --module "$module" --skip-test-records
done
bench --site her_ci execute heavy_equipment_rental.production_health.check
