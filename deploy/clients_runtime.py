"""Read the rendered client manifest using only the Python standard library."""

import json
import sys
from pathlib import Path

manifest = json.loads(Path(__file__).with_name("clients.json").read_text(encoding="utf-8"))
sites = manifest["sites"]

if len(sys.argv) == 2 and sys.argv[1] == "sites":
    for site in sites:
        print(site)
elif len(sys.argv) == 3 and sys.argv[1] == "check":
    site = sys.argv[2]
    installed = json.load(sys.stdin)[site]
    actual = set(installed) - {"frappe"}
    expected = set(sites[site]["apps"])
    if actual != expected:
        raise SystemExit(f"{site}: installed apps {sorted(actual)}; expected {sorted(expected)}")
    print(f"{site}: apps verified")
else:
    raise SystemExit("Usage: clients_runtime.py sites | check SITE")
