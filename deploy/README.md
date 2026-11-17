# HER production deployment

Push to `main` to validate, build a cached Docker image, install and migrate a disposable test site, run critical rental/accounting tests, publish the tested image to GHCR, and deploy its immutable digest over SSH. Pull requests build/test without deploying. Documentation-only pushes validate without rebuilding/deploying. Use **Actions → Test, build, deploy HER → Run workflow** to redeploy a revision on main.

Production: `https://cranes.arab-erp.com`, host `49.12.190.89` (`ssh hetzner3`), ARM64 host, stack `/opt/her`. Images and integration tests use native ARM64 GitHub runners. This is a clean site; no development company or demo transactions are copied. Apps: Frappe, ERPNext, `arab_erp_theme`, `heavy_equipment_rental`.

The domain root, `/app` and `/app/` redirect to `/app/crane-operations`, the main starting point. Frappe handles authentication and returns guests to that workspace after sign-in. Specific document/report links stay available. The maintenance response takes priority over entry redirects.

## Speed and versions

`apps.yaml` selects the Frappe branch (and optional `frappe_ref` commit pin) and the ordered applications, repositories and refs. CI resolves branch/tag refs to exact commits before building; full commit refs are also supported for apps. Those resolved inputs are baked into the tested image. HER's `ref: main` uses the exact checkout that triggered CI. This version-15 production stack requires ERPNext, arab_erp_theme and HER in that order; additional apps can follow their dependencies.

`Containerfile` caches the selected dependency apps and their assets in a stable runtime layer. HER updates use separate small layers. A changed dependency ref invalidates the appropriate cache layer. The calendar is built with Node 22 on GitHub. No build tools or Actions runner are installed on production.

The deployment uses Docker Compose with MariaDB 10.11, Redis, separate backend/workers/scheduler/websocket/frontend, and Caddy HTTPS. Only 80/443 and SSH are public; the application health port binds to loopback, and database/Redis have no published ports. Container logs rotate at 3 × 10 MB each. Docker starts at boot; services restart automatically.

## Which apps are installed

Edit the repository-root `apps.yaml`:

```yaml
frappe_branch: version-15
# Hold the currently validated production framework revision.
frappe_ref: b0b5b99a1d9d2cb3d54b32293d3854bf2c15f4a4
apps:
  - name: erpnext
    repo: https://github.com/frappe/erpnext
    # A branch/tag is also supported; pin production until its upgrade passes tests.
    ref: bfd8100d42162048248b7b947f2e21fdf7999a91
  - name: arab_erp_theme
    repo: https://github.com/00JIMMY00/arab_erp_theme
    ref: develop
  # HER comes from the exact checkout tested by this workflow.
  - name: heavy_equipment_rental
    repo: https://github.com/00JIMMY00/heavy_equipment_rental
    ref: main
```

`deploy/apps.py` validates/resolves this file in CI. The generated `deploy/runtime-manifest/` is ignored by Git and included in the image. `deploy/build_apps.py` downloads the listed dependencies; HER comes from the tested checkout. `deploy/site_apps.py` uses the same image manifest for new-site installation and for missing-app installation on existing sites, after the recovery snapshot and before migration. Both CI and production use it. Health checks require every listed app. Removing an installed app stops the rollout and restores its snapshot; app removal requires an explicit data migration. The old `clients.yaml` and `dependencies.json` are no longer used.

Production currently pins Frappe and ERPNext to their previously validated commits. Testing the latest ERPNext version-15 head exposed a double-capitalization regression, so that upgrade was blocked. The optional `frappe_ref` is a full framework commit SHA; omit it to track `frappe_branch`. Branch refs intentionally track their upstream branch on each runtime build; choose a full commit ref when you want to hold an app at a specific revision. For local image builds, first install PyYAML and run `python deploy/apps.py --output deploy/runtime-manifest`.

## Deployment transaction and recovery

1. Validate configuration, pull the candidate digest and check its contents while the current release serves traffic.
2. Enable proxy maintenance, stop application services and workers, then take and verify a SQL dump plus site files/configuration snapshot. DB/Redis and the proxy remain running.
3. Install the candidate configuration, migrate using a one-off container, and start its services.
4. Check all six app services, HTTP ping/login, database, Redis, installed applications and rental DocType tables.
5. Commit the image digest and reopen the site only after checks pass. On failure, restore the previous SQL database, site directory, Compose configuration and image; verify the restored release before reopening traffic. If restoration fails, maintenance remains enabled.

Failed initial installation has no previous site and remains behind maintenance for diagnosis. Backups live under `/opt/her/backups`; five complete pre-update recovery points are retained. Failed-release site files are retained alongside their recovery point. SQL and file archives are kept outside the site so migrations cannot delete them. These local backups protect updates; arrange off-server copies for host/disk loss.

After each successful release, retain the current image and the immediately previous successful image. Remove older HER image references and Compose orphans only. Database, site, Redis and Caddy volumes are never pruned. No global Docker prune is used.

## Credentials and operations

GitHub secrets: `DEPLOY_SSH_HOST`, `DEPLOY_SSH_USER`, `DEPLOY_SSH_KEY`, `DEPLOY_SSH_KNOWN_HOSTS`. The generated key has a forced deployment command and disables forwarding/interactive access. It accepts only a validated HER digest and the five expected archive files. Registry login uses the job's temporary `GITHUB_TOKEN`; its temporary Docker configuration is removed when deployment exits. No personal registry token is required.

The server's `/opt/her/.env` stores its generated database password (root-only). Retrieve the generated initial Administrator password over your existing administrator SSH connection:

```bash
ssh hetzner3 'cat /opt/her/state/administrator-password'
```

Change the password in Desk after first login. The file records the initial password only.

```bash
ssh hetzner3
cd /opt/her
docker compose ps
docker compose logs --tail 100 backend queue-short proxy
cat state/images.json
```

The installed `/opt/her/release.py` supports an explicit rollback rehearsal against the running digest. It backs up the current site, migrates it, deliberately fails after health checks, restores the snapshot, and exits unsuccessfully as expected:

```bash
python3 release.py IMAGE_DIGEST --incoming /opt/her --rollback-test
```

For a manual rollback after a previously accepted release, first enable `/opt/her/state/maintenance`, stop application services, and restore the chosen snapshot's `.env`, Compose configuration, site archive and SQL dump together. Merely starting an older image does **not** reverse migrations and must not be treated as a full rollback. Restoring an older snapshot after accepting new production transactions loses those later transactions; inspect/reconcile before doing that. Automatic rollback occurs while writes are paused, before a candidate is exposed to users.

## Verified production delivery

The [2026-11-16 workflow](https://github.com/00JIMMY00/heavy_equipment_rental/actions/runs/43907282490) passed all jobs, including an automatic update from the previous image. A live failure drill restored the SQL database, site files and configuration, removed temporary probes, and verified the recreated containers and public login. [Recorded evidence](../docs/PRODUCTION_DEPLOYMENT_20261116.json). The clean production site is ready for the native ERPNext setup wizard.

## Validation

```bash
python3 -m unittest deploy.test_rollout deploy.test_apps
APP_IMAGE=local/her:test DB_PASSWORD=test docker compose -f deploy/compose.yaml config --quiet
```

GitHub tests the actual production image with empty bind-mounted site/log directories and the same configurator as production, against a disposable database and runs rental workflow, maintenance lifecycle/posting and current operating-fee/automatic-settlement regressions. The older `test_partner_settlements` module still includes superseded service-date proration and implicit-sharing assumptions; it is not part of this release gate. `ci_fixtures.prepare` explicitly rejects any site except `her_ci`; fixture setup is never called by production install/migrate. `production_health.check` is a read-only Bench command, not a public API.

This workflow replaces the previous multi-client/client-manifest deployment. The remaining legacy retail workspace tools are not part of the production pipeline.
