# Contributing

Use Python 3.14.2–3.14.x. From a fresh checkout, run:

```sh
./scripts/setup stable
./scripts/check stable
./scripts/setup development
./scripts/check development
```

`setup` creates ignored `.venv/<baseline>/` environments, fetches full upstream Home Assistant Core at the commits in `core-baselines.json` into ignored `.test-core/<baseline>/`, installs matching dependencies, and generates translations. It refuses an existing Core checkout at a different commit. `check` runs the same gates as CI. Network access is needed for the initial setup; no sibling source checkout is needed.

Edit the canonical library in `dev/marstek-modbus`, Core overlay in `dev/home-assistant-core`, and icon in `assets/icon.png`. Run `./.venv/stable/bin/python scripts/sync.py` to regenerate the vendored library, converted tests, brand icon, and package hashes. Do not edit `custom_components/marstek/_vendor` by hand. The installable package is self-contained: HACS users do not install the library separately.

Include model, firmware, pack count, reproduction steps, and redacted diagnostics with bug reports. Do not commit MAC addresses, local endpoints, passwords, keys, or raw hardware captures. Read [Safety](SAFETY.md) before testing any writes.

The integration and adapted integration_blueprint material are MIT-licensed with retained attribution. The canonical and vendored device library are Apache-2.0 with their NOTICE. Home Battery Control is separate GPL-3.0 software; this project implements its entity naming contract without bundling its code.
