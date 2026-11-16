# HER production deployment

Push to `main` to validate, build a cached Docker image, install and migrate a disposable test site, run critical rental/accounting tests, publish the tested image to GHCR, and deploy its immutable digest over SSH. Pull requests build/test without deploying. Documentation-only pushes validate without rebuilding/deploying. Use **Actions → Test, build, deploy HER → Run workflow** to redeploy a revision on main.

Production: `https://cranes.arab-erp.com`, host `49.12.190.89` (`ssh hetzner3`), ARM64 host, stack `/opt/her`. Images and integration tests use native ARM64 GitHub runners. This is a clean site; no development company or demo transactions are copied. Apps: Frappe, ERPNext, `arab_erp_theme`, `heavy_equipment_rental`.

## Speed and versions

`Containerfile` caches Frappe, ERPNext, theme installation and their assets in a stable runtime layer. Each update builds/copies HER and its assets into separate small layers, so the server reuses the framework layers. Their exact source revisions are in `dependencies.json`, initially matching the development bench. Update these pins intentionally, then push main; the same installation/migration/tests gate framework upgrades. The calendar is built with Node 22 on GitHub. No build tools or Actions runner are installed on production.

The deployment uses Docker Compose with MariaDB 10.11, Redis, separate backend/workers/scheduler/websocket/frontend, and Caddy HTTPS. Only 80/443 and SSH are public; the application health port binds to loopback, and database/Redis have no published ports. Container logs rotate at 3 × 10 MB each. Docker starts at boot; services restart automatically.

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

## Validation

```bash
python3 -m unittest deploy.test_rollout
APP_IMAGE=local/her:test DB_PASSWORD=test docker compose -f deploy/compose.yaml config --quiet
```

GitHub tests the actual production image with empty bind-mounted site/log directories and the same configurator as production, against a disposable database and runs rental workflow, maintenance lifecycle/posting and current operating-fee/automatic-settlement regressions. The older `test_partner_settlements` module still includes superseded service-date proration and implicit-sharing assumptions; it is not part of this release gate. `ci_fixtures.prepare` explicitly rejects any site except `her_ci`; fixture setup is never called by production install/migrate. `production_health.check` is a read-only Bench command, not a public API.

This workflow replaces the previous multi-client/client-manifest deployment. Files such as the old client renderer and retail workspace tools are not part of the production pipeline.
