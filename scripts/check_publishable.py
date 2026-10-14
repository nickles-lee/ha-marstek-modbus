#!/usr/bin/env python3
"""Reject common personal endpoints and inline secrets in publishable files."""

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_IP = re.compile(
    r"\b(?:10\.\d{1,3}|192\.168|172\.(?:1[6-9]|2\d|3[01]))"
    r"\.\d{1,3}\.\d{1,3}\b"
)
MAC = re.compile(r"\b(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}\b")
KEY = re.compile(r"(?im)^\s*(?:key|password|token)\s*:\s*(\S.+?)\s*$")


def main() -> None:
    """Scan files Git would publish, excluding ignored development state."""
    names = subprocess.check_output(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=ROOT,
    ).split(b"\0")
    problems = []
    for raw in names:
        if not raw:
            continue
        relative = Path(raw.decode())
        path = ROOT / relative
        if not path.is_file():
            continue
        try:
            content = path.read_text()
        except UnicodeDecodeError, OSError:
            continue
        if PRIVATE_IP.search(content):
            problems.append(f"{relative}: private network address")
        if relative.suffix in {".yaml", ".yml"} and relative.parts[0] == "examples":
            for match in KEY.finditer(content):
                if not match.group(1).startswith("!secret "):
                    problems.append(f"{relative}: inline credential value")
        if relative.parts[0] in {"examples", "docs", "custom_components"}:
            if MAC.search(content):
                problems.append(f"{relative}: possible device MAC address")
        if "-----BEGIN " + "PRIVATE KEY-----" in content:
            problems.append(f"{relative}: private key")
    if problems:
        raise SystemExit("Publishable-file scan failed:\n" + "\n".join(problems))
    print("Publishable-file scan passed.")


if __name__ == "__main__":
    main()
