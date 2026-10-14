# Hardware validation status

The author reports about one week of real-world operation through this integration on Venus A, Venus E 2.0, and Venus E v3 batteries. This covers actual use, but does not establish that every register, control, operating mode, pack layout, and firmware revision has been individually verified. Venus D has **not** been tested on hardware because the author does not own one. Simulated tests cover all four implemented profiles.

| Model | Hardware status |
|---|---|
| Venus A | Used in real-world operation; individual measurements and controls can still vary by firmware and pack count. |
| Venus D | No hardware validation by this project. |
| Venus E 2.0 | Used in real-world operation through a Modbus TCP-to-RTU gateway. |
| Venus E v3 | Used in real-world operation. |

Before using a new model or firmware, check identity, SoC, signed AC/DC power, capacity, and temperatures against the device or app while idle, charging, and discharging. Keep control automations disabled until readings are credible. Test each write conservatively with explicit readback and retain a way to stop control independently of Home Assistant. See [Safety](../SAFETY.md) and [register uncertainties](register-uncertainties.md).

When reporting a discrepancy, include model, firmware, pack count, expected behavior, and redacted diagnostics. Never publish MAC addresses, endpoint details, or raw captures with identifying data.
