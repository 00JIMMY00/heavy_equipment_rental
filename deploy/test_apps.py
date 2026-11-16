import copy
import unittest
from unittest.mock import patch
from deploy.apps import validate, resolve
from deploy.site_apps import apply


class ManifestTests(unittest.TestCase):
    def setUp(self):
        import yaml
        from pathlib import Path
        self.data = yaml.safe_load(Path('apps.yaml').read_text())

    def test_current_manifest_and_extra_app(self):
        self.data['apps'].append(dict(name='extra', repo='https://github.com/example/extra', ref='main'))
        self.assertEqual(len(validate(self.data)['apps']), 4)

    def test_invalid_manifest_rejected(self):
        for change in (lambda d:d['apps'].append(d['apps'][0]), lambda d:d['apps'][0].update(repo='https://token@github.com/a/b'), lambda d:d.update(frappe_branch='version-16'), lambda d:d['apps'][0].update(ref='--evil')):
            data = copy.deepcopy(self.data)
            change(data)
            with self.assertRaises(ValueError): validate(data)

    def test_annotated_tag_resolves_to_commit(self):
        with patch('deploy.apps.subprocess.check_output', return_value='a'*40+'\trefs/tags/v1\n'+'b'*40+'\trefs/tags/v1^{}\n'):
            self.assertEqual(resolve('https://github.com/a/b', 'v1'), 'b'*40)

    def test_missing_app_installed_in_manifest_order(self):
        with patch('deploy.site_apps.names', return_value=['erpnext','arab_erp_theme','heavy_equipment_rental','extra']), patch('deploy.site_apps.subprocess.check_output', return_value='{"site":["frappe","erpnext","arab_erp_theme","heavy_equipment_rental"]}'), patch('deploy.site_apps.subprocess.call',return_value=0) as run:
            apply('site')
            run.assert_called_once_with(['bench','--site','site','install-app','extra'])

    def test_removed_app_rejected_without_uninstalling(self):
        with patch('deploy.site_apps.names', return_value=['erpnext']), patch('deploy.site_apps.subprocess.check_output', return_value='{"site":["frappe","erpnext","extra"]}'), patch('deploy.site_apps.subprocess.call') as run:
            with self.assertRaisesRegex(RuntimeError,'explicit data migration'): apply('site')
            run.assert_not_called()
