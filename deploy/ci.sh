#!/bin/bash
set -Eeuo pipefail
export CI=Yes
bash apps/heavy_equipment_rental/deploy/runtime/configure.sh
export HER_BOOTSTRAP_DB=ci-root HER_BOOTSTRAP_ADMIN=ci-admin
env/bin/python apps/heavy_equipment_rental/deploy/site_apps.py new her_ci
bench --site her_ci migrate
bench --site her_ci execute heavy_equipment_rental.ci_fixtures.prepare >/dev/null
bench --site her_ci set-config allow_tests true
for module in \
  heavy_equipment_rental.test_employee_entry \
  heavy_equipment_rental.heavy_equipment_rental.doctype.rental_contract.test_rental_workflow \
  heavy_equipment_rental.test_maintenance_lifecycle \
  heavy_equipment_rental.test_maintenance_posting \
  heavy_equipment_rental.test_operating_fees; do
  bench --site her_ci run-tests --module "$module" --skip-test-records
done
bench --site her_ci execute heavy_equipment_rental.production_health.check
