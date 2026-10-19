"""Exercise the release state machine without touching a Docker daemon."""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
IMAGE = "ghcr.io/00jimmy00/heavy_equipment_rental@sha256:"
V1, V2, V3 = (IMAGE + char * 64 for char in "abc")

FAKE_DOCKER = r'''#!/usr/bin/env python3
import json
import os
import sys
from pathlib import Path

path = Path(os.environ["FAKE_STATE"])
state = json.loads(path.read_text())
args = sys.argv[1:]
target = os.environ.get("APP_IMAGE", "")

if args[0] == "compose":
    args = args[3:]  # -f compose.yaml
    if args[:2] == ["ps", "-q"]:
        if state["current"]:
            print(args[2] + "-id")
    elif args[0] == "pull":
        if os.environ.get("FAIL_PULL") == "1":
            sys.exit(1)
    elif args[0] == "up":
        state["current"] = target
        state["up_count"] += 1
        path.write_text(json.dumps(state))
        if os.environ.get("FAIL_NEW_UP") == "1" and target == os.environ["TARGET_REF"]:
            sys.exit(1)
    elif args[0] == "exec":
        site = args[args.index("--site") + 1]
        if "backup" in args:
            state["backups"].append(site)
        elif "list-apps" in args:
            if os.environ.get("FAIL_SITES") == "1":
                sys.exit(1)
            apps = ["frappe", "erpnext"]
            if site.startswith("cranes"):
                apps.append("heavy_equipment_rental")
            print(json.dumps({site: apps}))
        elif "migrate" in args:
            state["migrations"].append(site)
        path.write_text(json.dumps(state))
    else:
        sys.exit("Unexpected compose args: " + repr(args))
elif args[0] == "inspect":
    if "{{.Config.Image}}" in args:
        print(state["current"])
    else:
        print("running")
elif args[:2] == ["image", "inspect"]:
    pass
elif args[:2] == ["image", "rm"]:
    state["removed"].append(args[2])
    path.write_text(json.dumps(state))
else:
    sys.exit("Unexpected docker args: " + repr(args))
'''

FAKE_CURL = r'''#!/usr/bin/env python3
import json
import os
from pathlib import Path

state = json.loads(Path(os.environ["FAKE_STATE"]).read_text())
if os.environ.get("FAIL_HEALTH") == "1" and state["current"] == os.environ["TARGET_REF"]:
    raise SystemExit(22)
'''


class RolloutTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / "bin").mkdir()
        for name, body in (("docker", FAKE_DOCKER), ("curl", FAKE_CURL)):
            path = self.root / "bin" / name
            path.write_text(body)
            path.chmod(0o755)
        for name in ("rollout.sh", "clients_runtime.py"):
            shutil.copy2(HERE / name, self.root / name)
        (self.root / "clients.json").write_text(json.dumps({"sites": {
            "alsakr.arab-erp.com": {"apps": ["erpnext"]},
            "cranes.arab-erp.com": {"apps": ["erpnext", "heavy_equipment_rental"]},
        }}))
        (self.root / "deploy.conf").write_text("HEALTH_TIMEOUT=0\n")
        (self.root / ".env").write_text(f"APP_IMAGE={V2}\nDB_PASSWORD=test\n")
        (self.root / "compose.yaml").write_text("services: {}\n")
        self.state_path = self.root / "state.json"
        self.state_path.write_text(json.dumps({
            "current": V2, "up_count": 0, "backups": [], "migrations": [], "removed": [],
        }))

    def run_rollout(self, target=V3, **flags):
        env = os.environ.copy()
        env.update({"PATH": str(self.root / "bin") + os.pathsep + env["PATH"],
                    "FAKE_STATE": str(self.state_path), "TARGET_REF": target})
        env.update(flags)
        return subprocess.run(["bash", "rollout.sh", target], cwd=self.root, env=env,
                              text=True, capture_output=True)

    def state(self):
        return json.loads(self.state_path.read_text())

    def test_pull_failure_keeps_old_container(self):
        result = self.run_rollout(FAIL_PULL="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.state()["current"], V2)
        self.assertEqual(self.state()["up_count"], 0)

    def test_failed_start_restores_previous_image(self):
        result = self.run_rollout(FAIL_NEW_UP="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.state()["current"], V2)
        self.assertEqual(self.state()["up_count"], 2)

    def test_failed_health_restores_previous_image(self):
        result = self.run_rollout(FAIL_HEALTH="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.state()["current"], V2)
        self.assertEqual(self.state()["up_count"], 2)

    def test_success_keeps_two_images(self):
        (self.root / ".image-history").write_text(V2 + "\n" + V1 + "\n")
        result = self.run_rollout()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.state()["current"], V3)
        self.assertEqual(self.state()["removed"], [V1])
        self.assertEqual((self.root / ".image-history").read_text().splitlines(), [V3, V2])
        self.assertEqual(len(self.state()["migrations"]), 2)

    def test_same_image_rerun_keeps_previous_image(self):
        (self.root / ".image-history").write_text(V2 + "\n" + V1 + "\n")
        result = self.run_rollout(target=V2)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.state()["removed"], [])
        self.assertEqual((self.root / ".image-history").read_text().splitlines(), [V2, V1])

    def test_first_release_can_be_rerun_after_sites_are_created(self):
        self.state_path.write_text(json.dumps({
            "current": "", "up_count": 0, "backups": [], "migrations": [], "removed": [],
        }))
        first = self.run_rollout(FAIL_SITES="1")
        self.assertNotEqual(first.returncode, 0)
        self.assertEqual(self.state()["current"], V3)
        second = self.run_rollout()
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(len(self.state()["migrations"]), 2)


if __name__ == "__main__":
    unittest.main()
