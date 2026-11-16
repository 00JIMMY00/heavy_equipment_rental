"""Validate apps.yaml in CI and freeze named refs before building an image."""
import argparse
import json
from pathlib import Path
import re
import subprocess


def validate(data):
    if not isinstance(data, dict) or set(data) != {'frappe_branch', 'apps'}:
        raise ValueError('Expected frappe_branch and apps')
    if data['frappe_branch'] != 'version-15':
        raise ValueError('This production stack supports version-15; framework-major upgrades require a stack upgrade')
    apps = data['apps']
    if not isinstance(apps, list) or not apps:
        raise ValueError('apps must be a nonempty list')
    names = []
    for app in apps:
        if not isinstance(app, dict) or set(app) != {'name', 'repo', 'ref'}:
            raise ValueError('Each app needs name, repo and ref')
        if not isinstance(app['name'], str) or not re.fullmatch(r'[a-z][a-z0-9_]*', app['name']) or app['name'] in names or app['name'] == 'frappe':
            raise ValueError('Invalid or duplicate app name')
        if not isinstance(app['repo'], str) or not re.fullmatch(r'https://github.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', app['repo']):
            raise ValueError('Use a public HTTPS GitHub repository URL without credentials')
        if not isinstance(app['ref'], str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_./-]*', app['ref']) or '..' in app['ref']:
            raise ValueError('Invalid Git ref')
        names.append(app['name'])
    required = ['erpnext', 'arab_erp_theme', 'heavy_equipment_rental']
    if any(name not in names for name in required) or [names.index(n) for n in required] != sorted(names.index(n) for n in required):
        raise ValueError('HER requires erpnext, arab_erp_theme and heavy_equipment_rental in that order')
    her = apps[names.index('heavy_equipment_rental')]
    if her['repo'] != 'https://github.com/00JIMMY00/heavy_equipment_rental' or her['ref'] != 'main':
        raise ValueError('HER must use this repository and ref main; the tested checkout supplies its exact commit')
    return data


def resolve(repo, ref):
    if re.fullmatch(r'[a-f0-9]{40}', ref):
        return ref
    rows = subprocess.check_output(['git', 'ls-remote', repo, 'refs/heads/'+ref, 'refs/tags/'+ref, 'refs/tags/'+ref+'^{}'], text=True).splitlines()
    refs = dict(row.split()[::-1] for row in rows)
    if 'refs/heads/'+ref in refs and 'refs/tags/'+ref in refs:
        raise ValueError('Ambiguous branch/tag: '+ref)
    revision = refs.get('refs/tags/'+ref+'^{}') or refs.get('refs/heads/'+ref) or refs.get('refs/tags/'+ref)
    if not revision or not re.fullmatch(r'[a-f0-9]{40}', revision):
        raise ValueError('Cannot resolve ref: '+repo+' '+ref)
    return revision


def main():
    import yaml
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    manifest = validate(yaml.safe_load(Path('apps.yaml').read_text()))
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    deps = {'frappe_branch': manifest['frappe_branch'], 'frappe_revision': resolve('https://github.com/frappe/frappe', manifest['frappe_branch']),
            'apps': [dict(app, revision=resolve(app['repo'], app['ref'])) for app in manifest['apps'] if app['name'] != 'heavy_equipment_rental']}
    (output/'dependencies.json').write_text(json.dumps(deps, sort_keys=True, indent=2)+'\n')
    (output/'apps.json').write_text(json.dumps(manifest, indent=2)+'\n')


if __name__ == '__main__':
    main()
