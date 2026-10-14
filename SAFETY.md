# Safety and no warranty

This software is provided **“as is,” without warranty of any kind to the extent permitted by law**. The MIT license for the integration and Apache-2.0 license for the device library contain the governing warranty and liability terms.

Marstek battery systems may store **5 kWh or more** and deliver **up to 2.5 kW**. Incorrect configuration, inaccurate measurements, unexpected commands, failed communication, or incompatible firmware can cause equipment damage, fire, injury, or property loss. **This integration is not a safety system.** Do not rely on it to enforce electrical or battery limits.

You are responsible for checking your exact model and firmware, following the manufacturer's instructions and site limits, retaining the battery's hardware protections, and supervising initial operation. Start with read-only monitoring. Before enabling automations or writes, confirm signs, units, power limits, and the device's actual readback; provide a way to stop control independently of Home Assistant.

Venus A, E 2.0, and E v3 have seen about a week of real-world use by the author. Venus D has **not** been hardware-tested by this project. That experience does not guarantee correct behavior for other hardware or firmware versions.
