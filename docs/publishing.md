# HACS publication path

The repository root is the HACS repository. HACS installs `custom_components/marstek`, including the generated `_vendor/marstek_modbus` copy, its Apache-2.0 license and NOTICE, and the brand icon. `dev/marstek-modbus` and `dev/home-assistant-core` stay in the same public repository as the authoritative source and test overlay; they are not separate HACS packages. Full upstream Home Assistant Core is downloaded by `./scripts/setup` into ignored `.test-core/` and is never committed.

## Custom repository

Publish this repository on GitHub with a clear description, `home-assistant` and `hacs` topics, and issues enabled. Push the checked source and let the test and validation Actions pass. Then add the GitHub URL in HACS as a custom Integration repository and test installing it on a clean Home Assistant 2026.9 or newer instance. A GitHub release is optional for this stage. These GitHub and live-install steps require a public remote and have not been performed by local checks.

## HACS default listing

After community use and issue resolution, confirm the HACS and hassfest Actions pass, publish a GitHub release, and submit the repository to the HACS default listing. The tag workflow creates a **draft** release so its archive can be reviewed; publish that draft before submission. Review the current HACS inclusion rules at submission time.

Hardware status and limitations are documented in [hardware validation](hardware-validation.md) and [register uncertainties](register-uncertainties.md). Venus D still needs physical validation by a D owner.
