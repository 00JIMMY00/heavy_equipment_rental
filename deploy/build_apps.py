"""Build-time dependency installation from CI's resolved manifest (stdlib only)."""
import json
import subprocess
from pathlib import Path


def run(*args):
    subprocess.run(args, check=True)


if __name__ == '__main__':
    pins = json.loads(Path('/tmp/dependencies.json').read_text())
    run('bench', 'init', '--frappe-branch', pins['frappe_branch'], '--no-procfile', '--no-backups', '--skip-redis-config-generation', '--skip-assets', 'frappe-bench')
    import os
    os.chdir('frappe-bench')
    for app in [dict(name='frappe', revision=pins['frappe_revision'])] + pins['apps']:
        name = app['name']
        if name != 'frappe':
            # Local clones allow branch, tag and full commit refs with the same behavior.
            source = '/tmp/her-source-' + name
            run('git', 'clone', '--no-checkout', '--depth=1', app['repo'], source)
            run('git', '-C', source, 'fetch', '--depth=1', 'origin', app['revision'])
            run('git', '-C', source, 'checkout', '-B', 'her-build', app['revision'])
            run('bench', 'get-app', '--branch', 'her-build', '--skip-assets', name, source)
        else:
            run('git', '-C', 'apps/frappe', 'fetch', '--depth=1', 'upstream', app['revision'])
            run('git', '-C', 'apps/frappe', 'checkout', '--detach', app['revision'])
        assert subprocess.check_output(['git', '-C', 'apps/'+name, 'rev-parse', 'HEAD'], text=True).strip() == app['revision']
    run('bench', 'setup', 'requirements', '--python')
    run('bench', 'setup', 'requirements', '--node')
