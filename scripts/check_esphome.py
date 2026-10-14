#!/usr/bin/env python3
"""Validate the public ESPHome example with disposable, non-personal secrets."""

import base64
import shutil
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples/lilygo-t-can485-modbus-bridge.yaml"
ESPHOME = ROOT / ".venv/esphome/bin/esphome"


def main() -> None:
    """Keep generated secrets and component downloads outside publishable files."""
    if not ESPHOME.is_file():
        raise SystemExit("Run ./scripts/setup first to install ESPHome")
    with TemporaryDirectory(prefix="marstek-esphome-") as directory:
        temp = Path(directory)
        config = temp / EXAMPLE.name
        shutil.copyfile(EXAMPLE, config)
        test_key = base64.b64encode(bytes(range(1, 33))).decode()
        (temp / "secrets.yaml").write_text(
            "marstek_bridge_api_key: " + test_key + "\n"
            "marstek_bridge_web_user: test-user\n"
            "marstek_bridge_web_password: test-password-only\n"
            "wifi_ssid: Test Network\n"
            "wifi_password: test-password-only\n"
        )
        result = subprocess.run(
            [str(ESPHOME), "config", str(config)],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode:
            raise SystemExit(result.stdout + result.stderr)
        for line in result.stderr.splitlines():
            if "WARNING" in line:
                print(line)
        print("ESPHome example configuration is valid.")


if __name__ == "__main__":
    main()
