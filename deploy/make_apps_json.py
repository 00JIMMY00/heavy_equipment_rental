"""Validate clients.yaml and render build/server manifests from it."""

import json
import os
import re
from pathlib import Path

import yaml

root = Path(__file__).resolve().parent.parent
manifest = yaml.safe_load((root / "clients.yaml").read_text(encoding="utf-8"))
if not isinstance(manifest, dict) or set(manifest) != {"apps", "sites"}:
    raise SystemExit("clients.yaml must contain exactly apps and sites")
apps = manifest["apps"]
sites = manifest["sites"]
if not isinstance(apps, dict) or not isinstance(sites, dict) or not sites:
    raise SystemExit("apps and sites must be nonempty mappings")

name_re = re.compile(r"^[a-z][a-z0-9_]*$")
site_re = re.compile(r"^[a-z0-9][a-z0-9.-]*[a-z0-9]$")
for name, source in apps.items():
    if not name_re.fullmatch(name) or not isinstance(source, dict) or set(source) != {"url", "ref"}:
        raise SystemExit(f"Invalid app entry: {name}")
    if not source["url"].startswith("https://github.com/") or not source["url"].endswith(".git"):
        raise SystemExit(f"App {name} must have a public GitHub clone URL")
    if not isinstance(source["ref"], str) or not source["ref"]:
        raise SystemExit(f"App {name} needs a ref")

needed = set()
for site, config in sites.items():
    if not site_re.fullmatch(site) or not isinstance(config, dict) or set(config) != {"apps"}:
        raise SystemExit(f"Invalid site entry: {site}")
    selected = config["apps"]
    if not isinstance(selected, list) or "erpnext" not in selected or len(selected) != len(set(selected)):
        raise SystemExit(f"Site {site} needs a unique app list containing erpnext")
    if not set(selected) <= set(apps):
        raise SystemExit(f"Site {site} names an app without a source")
    needed.update(selected)
if needed != set(apps):
    raise SystemExit("Remove unused app sources or assign them to a site")

app_commit = os.environ["APP_COMMIT"]
if not re.fullmatch(r"[a-f0-9]{40}", app_commit):
    raise SystemExit("APP_COMMIT must be a full Git commit SHA")

build_apps = []
for name, source in apps.items():
    if name in needed:
        ref = "main" if source["ref"] == "main-commit" else source["ref"]
        build_apps.append({"url": source["url"], "branch": ref})

output = Path("/tmp/apps.json")
output.write_text(json.dumps(build_apps), encoding="utf-8")
output.chmod(0o600)
(root / "deploy" / "clients.json").write_text(json.dumps({"sites": sites}, indent=2) + "\n", encoding="utf-8")
print(f"Validated {len(sites)} sites and {len(build_apps)} image apps")
