# Two-site production deployment

`clients.yaml` in the repository root is the source of truth. The release image
contains the union of apps required by both sites. Each site installs only its
listed apps:

| Site | Apps |
| --- | --- |
| `alsakr.arab-erp.com` | ERPNext |
| `cranes.arab-erp.com` | ERPNext, Heavy Equipment Rental |

To add another app later, add its public Git URL and ref under `apps`, add its
name to the intended site's list, release an image, and install the app on that
site. The deployment verifies the installed app sets; it never installs or
removes site apps automatically.

## GitHub settings

Add these **repository Actions secrets** (Settings → Secrets and variables →
Actions → Secrets):

| Kind | Name | Value |
| --- | --- | --- |
| Secret | `DEPLOY_SSH_KEY` | Complete contents of the dedicated, unencrypted SSH private key file |
| Secret | `DEPLOY_SSH_HOST` | Server address |
| Secret | `DEPLOY_SSH_USER` | Server login name |
| Secret | `DEPLOY_DIR` | Absolute path to the server deployment directory |
| Secret | `DEPLOY_SSH_KNOWN_HOSTS` | Verified SSH host-key line |

The private key must begin with `-----BEGIN OPENSSH PRIVATE KEY-----` and end
with `-----END OPENSSH PRIVATE KEY-----`. Paste the file contents, not its path,
public key, or a quoted/escaped string. The deploy script validates the key
before it connects. If using the GitHub CLI, copy the file without changing its
format: `gh secret set DEPLOY_SSH_KEY --repo 00JIMMY00/heavy_equipment_rental < ~/.ssh/heavy_equipment_rental_deploy_ed25519`.

`GITHUB_TOKEN` is provided by GitHub Actions and authenticates both publication
and the temporary server pull session. No GHCR personal token is needed. The
database password stays in the server's `.env`, never in GitHub.

## Initial server setup

The server uses Docker Compose and the existing Caddy container on Docker's
external `reverse_proxy` network. Copy `compose.yaml`, `rollout.sh`, and
`clients_runtime.py` to the server directory named by `DEPLOY_DIR`. Copy
`.env.example` to `.env`, generate a strong `DB_PASSWORD`, and copy
`deploy.conf.example` to `deploy.conf`. Keep both files readable only by the
deployment user.
The rollout copies the rendered `clients.json` from the release each time.

If using the existing Caddy server, add `Caddyfile.fragment` to its Caddyfile,
validate it, and reload Caddy. It preserves the original Host header and routes
only the two new names to `rental-frontend:8080`.

For a Cloudflare Tunnel on the same host, the frontend also listens on
`127.0.0.1:8083`. In the tunnel's **Public Hostnames**, route each hostname
(`cranes.arab-erp.com` and `alsakr.arab-erp.com`) to the HTTP service URL
`http://localhost:8083`. Cloudflare must create a DNS CNAME for each hostname
pointing to that tunnel; remove any conflicting A/AAAA/CNAME records first.
The tunnel terminates public HTTPS, so its service URL uses HTTP. Both sites
share the port and Frappe selects the site from the original Host header.
Use `alsakr` (starting with **a**) in the tunnel hostname, matching
`clients.yaml` and the Bench site directory.

The first `v*` tag is allowed to try deployment before site creation. It can
start the stack but will report failure because the sites do not exist yet. You
then create the sites in that stack and install their apps:

```bash
cd /path/to/deploy
set -a
. ./.env
set +a
read -rsp 'Alsakr Administrator password: ' ADMIN_PASSWORD; echo
docker compose exec backend bench new-site --db-root-password "$DB_PASSWORD" --admin-password "$ADMIN_PASSWORD" alsakr.arab-erp.com
unset ADMIN_PASSWORD
docker compose exec backend bench --site alsakr.arab-erp.com install-app erpnext

read -rsp 'Cranes Administrator password: ' ADMIN_PASSWORD; echo
docker compose exec backend bench new-site --db-root-password "$DB_PASSWORD" --admin-password "$ADMIN_PASSWORD" cranes.arab-erp.com
unset ADMIN_PASSWORD DB_PASSWORD
docker compose exec backend bench --site cranes.arab-erp.com install-app erpnext
docker compose exec backend bench --site cranes.arab-erp.com install-app heavy_equipment_rental
```

Rerun the failed deployment job. It rechecks installed apps, migrates both
sites, and verifies both HTTPS endpoints even when the image digest is already
running.

## Release behavior

Push a `v*` tag from `main`. CI runs
Bench tests, checks the frontend assets, builds and smoke-tests the image, then
pushes it to GHCR. The deployment uses the registry digest, which identifies
the exact image that passed the smoke test.

The server pulls before changing containers. It backs up both sites, recreates
app services, verifies their installed app sets, migrates both sites, and checks
each site's ping endpoint on the local frontend port with its Host header. On
startup, migration, or health failure, it restores the previous image digest.
Docker Compose removes replaced app containers. After success, only the current
and previous app images are retained; the image from two successful releases
ago is removed. Database,
Redis, and site volumes are never pruned.

Container rollback does not reverse database changes. Site backups are created
before migration and remain available for a reviewed restore. Keep independent
off-server backups too.
