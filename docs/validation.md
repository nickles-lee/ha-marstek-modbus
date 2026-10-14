# Validation and release checks

A fresh checkout contains the canonical device library in `dev/marstek-modbus`, the Marstek-only Core overlay in `dev/home-assistant-core`, the generated HACS integration in `custom_components/marstek`, and converted integration tests in `tests/marstek`. Full Home Assistant Core is fetched into ignored `.test-core/<baseline>/` directories by `./scripts/setup`.

Run `./scripts/setup stable` followed by `./scripts/check stable` for Home Assistant 2026.9.0 and modbus-connection 4.10.0. Repeat with `development` for the pinned development Core commit and modbus-connection 4.12.1. `core-baselines.json` records exact Core commits and transport versions. Setup also creates an ignored virtual environment and generates development translations. It checks an existing Core checkout against the pinned commit.

The check command runs source synchronization and package checks, ESPHome configuration validation with disposable secrets, Ruff, library mypy and tests, integration tests in the pinned Core harness, archive installation smoke, and local hassfest. GitHub CI runs the same commands from a fresh checkout. The HACS and hassfest GitHub actions validate repository metadata after publication.

Both pinned local baselines pass the check command as verified on 14 October 2026: 40 library tests, 84 integration tests, 84 archive smoke tests, lint, typing, source and checksum parity, the publishable-file scan, ESPHome configuration validation, and hassfest with zero invalid integrations. The check command loads the canonical library source explicitly so validation does not depend on an editable-install path file in the local environment. The wrong-revision checkout guard was also exercised. GitHub Actions and a live HACS custom-repository install still require the public repository.

The author reports about a week of live use on Venus A, E 2.0, and E v3. Venus D is not hardware-tested. See [hardware status](hardware-validation.md), [register uncertainties](register-uncertainties.md), and [Safety](../SAFETY.md). No broad claim of per-register or per-firmware validation follows from a passing test suite.
