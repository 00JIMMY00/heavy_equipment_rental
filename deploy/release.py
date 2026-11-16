#!/usr/bin/env python3
"""Transactional single-site deployment. Run as root on the production host."""
import argparse
import fcntl
import gzip
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import tarfile
import time
import urllib.request

IMAGE = re.compile(r"ghcr\.io/00jimmy00/heavy_equipment_rental@sha256:[a-f0-9]{64}\Z")
SERVICES = ['backend', 'frontend', 'websocket', 'queue-short', 'queue-long', 'scheduler']


class Release:
    def __init__(self, root, incoming, target, rollback_test=False):
        self.root, self.incoming, self.target = Path(root), Path(incoming), target
        self.rollback_test = rollback_test
        self.old_env = self.read_env()
        self.old = self.old_env.get('APP_IMAGE', '')
        self.site = self.old_env.get('SITE_NAME', 'cranes.arab-erp.com')
        if not re.fullmatch(r'[a-z0-9.-]+', self.site):
            raise ValueError('Invalid site name')
        self.snapshot = None
        self.changed = False
        self.maintenance = self.root / 'state/maintenance'

    def read_env(self):
        return dict(line.split('=', 1) for line in (self.root / '.env').read_text().splitlines()
                    if line and not line.startswith('#'))

    def run(self, *args, capture=False, **kwargs):
        return subprocess.run(args, cwd=self.root, check=True, text=True,
                              stdout=subprocess.PIPE if capture else None, **kwargs)

    def compose(self, *args, image=None, candidate=False, capture=False):
        config = self.incoming / 'compose.yaml' if candidate else self.root / 'compose.yaml'
        env = os.environ.copy()
        env['APP_IMAGE'] = image or self.target
        return self.run('docker', 'compose', '--project-directory', str(self.root),
                        '--env-file', str(self.root / '.env'), '-p', 'her', '-f', str(config),
                        *args, env=env, capture=capture)

    def bench(self, *args, image=None):
        return self.compose('run', '--rm', '--no-deps', 'backend', 'bench',
                            '--site', self.site, *args, image=image)

    def database_command(self, program):
        # Password is expanded inside the DB container and never logged or put in host argv.
        return ['docker', 'compose', '--project-directory', str(self.root),
                '--env-file', str(self.root / '.env'), '-p', 'her', '-f', str(self.root / 'compose.yaml'),
                'exec', '-T', 'db', 'sh', '-ec', program]

    def backup(self):
        stamp = time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())
        self.snapshot = self.root / 'backups' / (stamp + '-' + self.old[-12:])
        self.snapshot.mkdir(mode=0o700)
        for name in ('.env', 'compose.yaml', 'Caddyfile'):
            shutil.copy2(self.root / name, self.snapshot / name)
        config = json.loads((self.root / 'sites' / self.site / 'site_config.json').read_text())
        database = config['db_name']
        if not re.fullmatch(r'[A-Za-z0-9_]+', database):
            raise ValueError('Invalid database name')
        dump = ('exec mariadb-dump -uroot -p"$MARIADB_ROOT_PASSWORD" '
                '--single-transaction --routines --triggers --events --hex-blob '
                '--add-drop-database --databases ' + database)
        env = os.environ.copy()
        env['APP_IMAGE'] = self.old
        proc = subprocess.Popen(self.database_command(dump), cwd=self.root, env=env, stdout=subprocess.PIPE)
        with gzip.open(self.snapshot / 'database.sql.gz', 'wb') as dest:
            shutil.copyfileobj(proc.stdout, dest)
        if proc.wait():
            raise RuntimeError('Database backup failed')
        self.run('tar', '--exclude=sites/assets', '--exclude=*/private/backups',
                 '-czf', str(self.snapshot / 'sites.tar.gz'), 'sites')
        self.verify_backup(self.snapshot)
        (self.snapshot / 'release.json').write_text(json.dumps({'image': self.old, 'site': self.site}) + '\n')
        print('Verified recovery snapshot: ' + str(self.snapshot), flush=True)

    @staticmethod
    def verify_backup(path):
        with gzip.open(path / 'database.sql.gz', 'rb') as src:
            size = 0
            while chunk := src.read(1024 * 1024):
                size += len(chunk)
            if size < 100:
                raise RuntimeError('Database backup is empty')
        with tarfile.open(path / 'sites.tar.gz', 'r:gz') as archive:
            if not any(item.name.endswith('/site_config.json') for item in archive):
                raise RuntimeError('Site configuration missing from backup')

    def stop(self):
        self.compose('stop', 'scheduler', 'queue-short', 'queue-long', 'frontend', 'websocket', 'backend', image=self.old or self.target)

    def healthy(self):
        rows = self.compose('ps', '--format', 'json', capture=True).stdout.strip()
        parsed = json.loads(rows) if rows.startswith('[') else [json.loads(row) for row in rows.splitlines()]
        running = {row['Service'] for row in parsed if row['State'] == 'running'}
        if not set(SERVICES).issubset(running):
            return False
        request = urllib.request.Request('http://127.0.0.1:8083/api/method/ping', headers={'Host': self.site})
        with urllib.request.urlopen(request, timeout=8) as response:
            if json.load(response).get('message') != 'pong':
                return False
        with urllib.request.urlopen(urllib.request.Request('http://127.0.0.1:8083/login', headers={'Host': self.site}), timeout=8) as response:
            if response.status != 200:
                return False
        # Exercise DB, Redis and installed-app metadata, rather than trusting ping alone.
        self.compose('exec', '-T', 'backend', 'bench', '--site', self.site,
                     'execute', 'heavy_equipment_rental.production_health.check')
        return True

    def wait_healthy(self):
        deadline = time.monotonic() + 180
        while time.monotonic() < deadline:
            try:
                if self.healthy():
                    return
            except (subprocess.CalledProcessError, OSError, ValueError):
                pass
            time.sleep(5)
        raise RuntimeError('Production health checks timed out')

    def restore(self):
        print('Restoring previous database, files, configuration and image', flush=True)
        self.stop()
        for name in ('.env', 'compose.yaml', 'Caddyfile'):
            shutil.copy2(self.snapshot / name, self.root / name)
        # Keep failed-release files for investigation. Never overlay restored uploads.
        failed_sites = self.root / 'backups' / (self.snapshot.name + '-failed-sites')
        (self.root / 'sites').rename(failed_sites)
        self.run('tar', '-xzf', str(self.snapshot / 'sites.tar.gz'))
        env = os.environ.copy()
        env['APP_IMAGE'] = self.old
        proc = subprocess.Popen(self.database_command('exec mariadb -uroot -p"$MARIADB_ROOT_PASSWORD"'),
                                cwd=self.root, env=env, stdin=subprocess.PIPE)
        try:
            with gzip.open(self.snapshot / 'database.sql.gz', 'rb') as src:
                shutil.copyfileobj(src, proc.stdin)
        finally:
            proc.stdin.close()
        if proc.wait():
            raise RuntimeError('Database restoration failed; maintenance remains enabled')
        self.compose('run', '--rm', '--no-deps', 'configurator', image=self.old)
        self.bench('set-maintenance-mode', 'off', image=self.old)
        self.compose('up', '-d', '--pull', 'never', '--remove-orphans', image=self.old)
        self.compose('exec', '-T', 'proxy', 'caddy', 'reload', '--config', '/etc/caddy/Caddyfile', image=self.old)
        self.target = self.old
        self.wait_healthy()
        self.maintenance.unlink(missing_ok=True)
        print('Rollback verified; previous release is serving again.', flush=True)

    def cleanup(self):
        history_path = self.root / 'state/images.json'
        history = json.loads(history_path.read_text()) if history_path.exists() else []
        keep = list(dict.fromkeys([self.target, self.old] + history))
        keep = [item for item in keep if IMAGE.fullmatch(item)][:2]
        history_path.write_text(json.dumps(keep) + '\n')
        # Compare image IDs so stale sha-* tags cannot keep old image layers alive.
        protected = set(self.run('docker', 'image', 'inspect', '--format', '{{.Id}}',
                                 *keep, capture=True).stdout.splitlines())
        result = self.run('docker', 'image', 'ls', '--no-trunc', '--digests',
                          '--format', '{{json .}}', capture=True)
        remove = set()
        for line in result.stdout.splitlines():
            item = json.loads(line)
            if item['Repository'] != 'ghcr.io/00jimmy00/heavy_equipment_rental' or item['ID'] in protected:
                continue
            if item['Tag'] != '<none>':
                remove.add(item['Repository'] + ':' + item['Tag'])
            ref = item['Repository'] + '@' + item['Digest']
            if IMAGE.fullmatch(ref):
                remove.add(ref)
        if remove:
            subprocess.run(['docker', 'image', 'rm', *sorted(remove)], cwd=self.root, check=False)
        # Retain the latest five complete recovery points, including failed-release files.
        backups = sorted(path for path in (self.root / 'backups').iterdir() if (path / 'release.json').exists())
        for backup in backups[:-5]:
            shutil.rmtree(backup)
            shutil.rmtree(backup.with_name(backup.name + '-failed-sites'), ignore_errors=True)

    def deploy(self):
        self.compose('config', '--quiet', candidate=True)
        try:
            self.run('docker', 'image', 'inspect', self.target, capture=True)
        except subprocess.CalledProcessError:
            self.run('docker', 'pull', self.target)
        # Detect empty/incorrect images before touching the running site.
        self.run('docker', 'run', '--rm', '--entrypoint', 'bash', self.target, '-ec',
                 'test -s apps/heavy_equipment_rental/.source-commit; '
                 'test -f apps/heavy_equipment_rental/heavy_equipment_rental/production_health.py; '
                 'grep -qx arab_erp_theme sites/apps.txt; grep -qx erpnext sites/apps.txt')
        installed = (self.root / 'sites' / self.site / 'site_config.json').exists()
        if installed and not IMAGE.fullmatch(self.old):
            raise RuntimeError('Existing site requires a valid previous image in .env')
        self.maintenance.touch(mode=0o644)
        try:
            if installed:
                self.bench('set-maintenance-mode', 'on', image=self.old)
                self.stop()
                self.backup()
            self.changed = True
            for name in ('compose.yaml', 'Caddyfile'):
                source, destination = self.incoming / name, self.root / name
                if source.resolve() != destination.resolve():
                    shutil.copy2(source, destination)
            self.compose('up', '-d', '--pull', 'missing', 'db', 'redis-cache', 'redis-queue', 'proxy')
            self.compose('exec', '-T', 'proxy', 'caddy', 'reload', '--config', '/etc/caddy/Caddyfile')
            self.compose('run', '--rm', 'configurator')
            if not installed:
                # The generated password lives only on the server, outside the repository.
                password = (self.root / 'state/administrator-password').read_text().strip()
                root_password = self.old_env['DB_PASSWORD']
                os.environ['HER_BOOTSTRAP_ADMIN'] = password
                os.environ['HER_BOOTSTRAP_DB'] = root_password
                try:
                    self.compose('run', '--rm', '--no-deps', '-e', 'HER_BOOTSTRAP_ADMIN',
                                 '-e', 'HER_BOOTSTRAP_DB', 'backend', 'bash', '-ec',
                                 'bench new-site "$1" --db-root-password "$HER_BOOTSTRAP_DB" '
                                 '--admin-password "$HER_BOOTSTRAP_ADMIN" '
                                 '--mariadb-user-host-login-scope=% --install-app erpnext '
                                 '--install-app arab_erp_theme --install-app heavy_equipment_rental',
                                 'bootstrap', self.site)
                finally:
                    os.environ.pop('HER_BOOTSTRAP_ADMIN', None)
                    os.environ.pop('HER_BOOTSTRAP_DB', None)
                self.bench('set-config', 'host_name', 'https://' + self.site)
            self.bench('set-config', '-p', 'developer_mode', '0')
            self.bench('set-config', '-p', 'allow_tests', '0')
            self.bench('migrate')
            self.bench('set-maintenance-mode', 'off')
            self.bench('enable-scheduler')
            self.compose('up', '-d', '--pull', 'never', '--remove-orphans')
            self.wait_healthy()
            if self.rollback_test:
                raise RuntimeError('Deliberate rollback drill after migration')
        except BaseException:
            if installed and self.snapshot and (self.snapshot / 'release.json').exists() and self.changed:
                self.restore()
            elif installed and not self.changed:
                self.bench('set-maintenance-mode', 'off', image=self.old)
                self.compose('up', '-d', '--pull', 'never', image=self.old)
                self.maintenance.unlink(missing_ok=True)
            # Failed first installs stay behind maintenance for diagnosis/retry.
            raise
        env = self.read_env()
        env['APP_IMAGE'] = self.target
        temp = self.root / '.env.next'
        temp.write_text(''.join(key + '=' + value + '\n' for key, value in env.items()))
        temp.chmod(0o600)
        temp.replace(self.root / '.env')
        self.maintenance.unlink(missing_ok=True)
        try:
            self.cleanup()
        except (OSError, ValueError, subprocess.CalledProcessError) as error:
            print('Release is healthy; cleanup needs attention: ' + str(error), file=sys.stderr)
        print('Deployment verified: ' + self.target, flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('image')
    parser.add_argument('--root', default='/opt/her')
    parser.add_argument('--incoming', default=str(Path(__file__).resolve().parent))
    parser.add_argument('--rollback-test', action='store_true')
    args = parser.parse_args()
    if not IMAGE.fullmatch(args.image):
        parser.error('An immutable HER image digest is required')
    def interrupted(signum, frame):
        raise InterruptedError('Deployment interrupted by signal ' + str(signum))
    for signum in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(signum, interrupted)
    root = Path(args.root).resolve()
    os.umask(0o077)
    with (root / 'state/deploy.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        Release(root, Path(args.incoming).resolve(), args.image, args.rollback_test).deploy()


if __name__ == '__main__':
    main()
