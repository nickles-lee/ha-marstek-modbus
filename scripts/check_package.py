#!/usr/bin/env python3
"""Validate the self-contained package against committed source checksums."""

import ast
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
expected = json.loads((root / "source-hashes.json").read_text())
package = root / "custom_components/marstek"
if not (root / "LICENSE").read_text().startswith("MIT License"):
    raise SystemExit("Root integration license must be MIT.")
canonical_library = root / "dev/marstek-modbus"
if "Apache License" not in (canonical_library / "LICENSE").read_text():
    raise SystemExit("Canonical device-library license must be Apache-2.0.")
for name in ("LICENSE", "NOTICE"):
    if (package / "_vendor/marstek_modbus" / name).read_bytes() != (
        canonical_library / name
    ).read_bytes():
        raise SystemExit(f"Vendored {name} differs from the canonical library.")
actual = {
    p.relative_to(package).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
    for p in package.rglob("*")
    if p.is_file() and "__pycache__" not in p.parts
}
if actual != expected:
    raise SystemExit(
        "Source checksums differ; run scripts/sync.py from the source workspace."
    )
manifest = json.loads((package / "manifest.json").read_text())
if manifest["requirements"]:
    raise SystemExit("The HACS package must not install the device library separately.")
for source in package.glob("*.py"):
    for node in ast.walk(ast.parse(source.read_text())):
        if isinstance(node, ast.Import) and any(
            alias.name == "marstek_modbus" or alias.name.startswith("marstek_modbus.")
            for alias in node.names
        ):
            raise SystemExit(f"Non-vendored device-library import in {source}")
        if (
            isinstance(node, ast.ImportFrom)
            and node.level == 0
            and (
                node.module == "marstek_modbus"
                or (node.module or "").startswith("marstek_modbus.")
            )
        ):
            raise SystemExit(f"Non-vendored device-library import in {source}")
print("Vendored package checksums match.")
