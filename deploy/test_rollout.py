"""Exercise failure ordering and recovery without a Docker daemon."""
import gzip
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch
from deploy.release import IMAGE, Release

OLD = 'ghcr.io/00jimmy00/heavy_equipment_rental@sha256:' + 'a' * 64
NEW = 'ghcr.io/00jimmy00/heavy_equipment_rental@sha256:' + 'b' * 64


class RolloutTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for directory in ('state', 'backups', 'sites/cranes.arab-erp.com', 'incoming'):
            (self.root / directory).mkdir(parents=True, exist_ok=True)
        (self.root / '.env').write_text(f'APP_IMAGE={OLD}\nDB_PASSWORD=secret\n')
        (self.root / 'sites/cranes.arab-erp.com/site_config.json').write_text('{"db_name":"_test"}')
        self.release = Release(self.root, self.root / 'incoming', NEW)
        self.calls = []
        self.release.run = lambda *args, **kwargs: self.calls.append(('run', args))
        self.release.compose = lambda *args, **kwargs: self.calls.append(('compose', args))
        self.release.bench = lambda *args, **kwargs: self.calls.append(('bench', args))
        self.release.stop = lambda: self.calls.append(('stop', ()))
        self.release.restore = lambda: self.calls.append(('restore', ()))
        self.release.wait_healthy = lambda: self.calls.append(('healthy', ()))
        self.release.cleanup = lambda: self.calls.append(('cleanup', ()))
        for name in ('compose.yaml', 'Caddyfile'):
            (self.root / name).write_text('old')
            (self.root / 'incoming' / name).write_text('new')

    def snapshot(self):
        self.calls.append(('backup', ()))
        self.release.snapshot = self.root / 'backups/test'
        self.release.snapshot.mkdir()
        (self.release.snapshot / 'release.json').write_text('{}')

    def test_success_snapshots_before_switch_and_commits_after_health(self):
        self.release.backup = self.snapshot
        self.release.deploy()
        events = [item[0] for item in self.calls]
        self.assertLess(events.index('stop'), events.index('backup'))
        self.assertLess(events.index('backup'), events.index('healthy'))
        self.assertEqual(self.release.read_env()['APP_IMAGE'], NEW)
        self.assertFalse(self.release.maintenance.exists())

    def test_failed_migration_restores_snapshot_without_advancing_image(self):
        self.release.backup = self.snapshot
        original = self.release.bench
        def fail(*args, **kwargs):
            if args == ('migrate',):
                raise RuntimeError('broken migration')
            return original(*args, **kwargs)
        self.release.bench = fail
        with self.assertRaisesRegex(RuntimeError, 'broken migration'):
            self.release.deploy()
        self.assertIn(('restore', ()), self.calls)
        self.assertEqual(self.release.read_env()['APP_IMAGE'], OLD)
        self.assertNotIn(('cleanup', ()), self.calls)

    def test_backup_failure_resumes_old_release_without_migration(self):
        def fail():
            raise RuntimeError('disk full')
        self.release.backup = fail
        with self.assertRaisesRegex(RuntimeError, 'disk full'):
            self.release.deploy()
        self.assertNotIn(('bench', ('migrate',)), self.calls)
        self.assertNotIn(('restore', ()), self.calls)
        self.assertEqual((self.root / 'compose.yaml').read_text(), 'old')
        self.assertFalse(self.release.maintenance.exists())

    def test_pull_failure_never_enters_maintenance(self):
        def fail(*args, **kwargs):
            raise RuntimeError('registry unavailable')
        self.release.run = fail
        with self.assertRaises(RuntimeError):
            self.release.deploy()
        self.assertFalse(self.release.maintenance.exists())
        self.assertNotIn(('stop', ()), self.calls)

    def test_failed_rollback_leaves_maintenance_active(self):
        self.release.backup = self.snapshot
        self.release.rollback_test = True
        def fail():
            raise RuntimeError('restore failed')
        self.release.restore = fail
        with self.assertRaisesRegex(RuntimeError, 'restore failed'):
            self.release.deploy()
        self.assertTrue(self.release.maintenance.exists())
        self.assertEqual(self.release.read_env()['APP_IMAGE'], OLD)

    def test_corrupt_backup_is_rejected(self):
        path = self.root / 'backups'
        (path / 'database.sql.gz').write_bytes(b'corrupt')
        with self.assertRaises(gzip.BadGzipFile):
            Release.verify_backup(path)

    def test_cleanup_keeps_two_images_and_never_prunes_volumes(self):
        self.release.cleanup = Release.cleanup.__get__(self.release)
        extra = 'ghcr.io/00jimmy00/heavy_equipment_rental@sha256:' + 'c' * 64
        class Result:
            stdout = NEW + '\n' + OLD + '\n' + extra + '\nother/repository@sha256:' + 'd'*64
        self.release.run = lambda *args, **kwargs: Result()
        with patch('deploy.release.subprocess.run') as run:
            self.release.cleanup()
        self.assertEqual(json.loads((self.root / 'state/images.json').read_text()), [NEW, OLD])
        run.assert_called_once_with(['docker', 'image', 'rm', extra], cwd=self.root, check=False)

    def test_only_immutable_her_images_accepted(self):
        self.assertTrue(IMAGE.fullmatch(NEW))
        self.assertFalse(IMAGE.fullmatch('ghcr.io/00jimmy00/heavy_equipment_rental:latest'))
        self.assertFalse(IMAGE.fullmatch(NEW + ';id'))
