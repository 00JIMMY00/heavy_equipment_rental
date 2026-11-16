"""Use the immutable image's app manifest for new sites and safe app additions."""
import json
import os
from pathlib import Path
import subprocess
import sys


def names():
    path = Path(__file__).resolve().parent / 'runtime-manifest/apps.json'
    return [app['name'] for app in json.loads(path.read_text())['apps']]


def apply(site, create=False):
    wanted = names()
    if create:
        command = ['bench', 'new-site', site, '--db-root-password', os.environ['HER_BOOTSTRAP_DB'],
                   '--admin-password', os.environ['HER_BOOTSTRAP_ADMIN'], '--mariadb-user-host-login-scope=%']
        for app in wanted:
            command += ['--install-app', app]
    else:
        result = subprocess.check_output(['bench', '--site', site, 'list-apps', '-f', 'json'], text=True)
        installed = json.loads(result)[site]
        removed = set(installed) - set(wanted) - {'frappe'}
        if removed:
            raise RuntimeError('Removing installed apps requires an explicit data migration: '+', '.join(sorted(removed)))
        command = ['bench', '--site', site, 'install-app'] + [app for app in wanted if app not in installed]
        if len(command) == 4:
            return
    # Do not include bootstrap passwords in exception messages.
    if subprocess.call(command):
        raise RuntimeError('Site application installation failed')


if __name__ == '__main__':
    apply(sys.argv[2], create=sys.argv[1] == 'new')
