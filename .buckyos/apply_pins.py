"""Override keys of a conda-forge .ci_support/<config>.yaml with .buckyos/pins/<subdir>.json.

usage: apply_pins.py <.ci_support/config.yaml> <pins.json>

The CI job runs this on its checkout before conda-forge's build script reads the
file; nothing is committed. A .ci_support file is a flat map of keys to one-item
lists ("key:\\n- value"), so it is edited as text and needs no YAML library.
"""
import json
import re
import sys
from pathlib import Path

config, pins = Path(sys.argv[1]), json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
lines = config.read_text(encoding="utf-8").splitlines()
for key, value in sorted(pins.items()):
    item = f"- '{value}'"
    at = next((i for i, line in enumerate(lines) if line == f"{key}:"), None)
    if at is None:
        lines += [f"{key}:", item]
        print(f"{key}: added {value}")
        continue
    end = at + 1
    while end < len(lines) and re.match(r"^- ", lines[end]):
        end += 1
    if end - at != 2:
        raise SystemExit(f"{config}: {key} has {end - at - 1} values; a pin replaces exactly one")
    print(f"{key}: {lines[at + 1][2:]} -> {value}")
    lines[at + 1] = item
config.write_text("\n".join(lines) + "\n", encoding="utf-8")
