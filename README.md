# Marstek for Home Assistant

Local Modbus TCP integration for Marstek Venus A, Venus D, Venus E 2.0 and Venus E v3 batteries, with direct Home Battery Control entity compatibility.

**Minimum Home Assistant version: 2026.9.0.** The integration uses Home Assistant’s Modbus transport. The author has around three weeks of real-world usage with Venus A, E 2.0, and E v3 batteries. Venus D has not been hardware-tested because the author does not own one.

**Safety and no warranty:** This software is provided “as is,” without warranty to the extent permitted by law. These batteries may store 5 kWh or more and deliver up to 2.5 kW of power at once. Incorrect readings or commands can cause equipment damage, fire, or injury. Follow manufacturer limits, keep hardware protections in place, and supervise initial operation. This integration is not a safety system. Read [Safety](SAFETY.md) before enabling controls. Remember that two batteries on a single phase can blow a 25A main fuse and require a €100 electrician visit!

## Installation

With HACS installed, open the Marstek repository using this button:

[![Open Marstek in HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=nickles-lee&repository=ha-marstek-modbus&category=integration)

1. Open the repository using the button above, or add https://github.com/nickles-lee/ha-marstek-modbus manually as a custom HACS repository, category Integration.
2. Install Marstek and restart Home Assistant.
3. Add Marstek under Settings → Devices & services.
4. Enter the battery or gateway TCP host, port (normally 502), unit ID (normally 1), model and actual pack count. Select `e_v2` and one pack for Venus E 2.0.
5. Accept the next free HBC battery number or choose another unused N.

After installing Marstek and restarting Home Assistant, this button opens the integration setup:

[![Add Marstek to Home Assistant](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=marstek)

For local testing, copy custom_components/marstek into your configuration's custom_components directory and restart. The generated ZIP contains custom_components/marstek and can be extracted into the configuration directory.

The Python device library is vendored. There is no unpublished device-package dependency to install. Core's modbus integration supplies the transport. Modbus TCP endpoints include gateways translating TCP to RS485/RTU; a transparent RTU-over-TCP serial bridge is not the same protocol.

Remove or disable an old package/integration exposing the same marstek_mN entity IDs before assigning that number. The integration refuses collisions instead of silently creating _2 IDs.

## Supported profiles

| Model | Packs | Cells per pack | Maximum setpoint |
|---|---:|---:|---:|
| Venus A | 1–6 | 13 | 1500 W |
| Venus D | 1–7 | 16 | 2500 W |
| Venus E 2.0 | 1 | Not exposed | 2500 W |
| Venus E v3 | 1 | 16 | 2500 W |

Extended diagnostics are disabled by default. Hardware experience is limited to the author’s A, E 2.0, and E v3 devices; firmware variants and individual fields may behave differently. Venus D remains untested on hardware.

## Home Battery Control

The power controls and telemetry in the [HBC integration contract](https://docs.homebatterycontrol.com/09-for-integrators) is present by default with prefix marstek_mN:

- Sensors: device_name, battery_state_of_charge, battery_voltage, battery_total_energy, ac_power, battery_power, inverter_state_number, inverter_state, battery_remaining_capacity.
- Numbers: max_charge_power, max_discharge_power, forcible_charge_power, forcible_discharge_power, charging_cutoff_capacity, discharging_cutoff_capacity.
- Selects: rs485_control_mode, user_work_mode, forcible_charge_discharge, backup_function.

Force-charge-to-SoC (`42011`) is commented out for all models because each write activates an alternative SoC-target mode. It is excluded from polling, entities and managed heartbeats, and saved goals for it are discarded on upgrade. Charge cutoff (`44000`, 80–100%) and discharge cutoff (`44001`, 12–30%) are available in 0.1% steps. On firmware that accepts the registers, these adopt existing battery values and follow the same RS485-gated goal policy as the power controls. Cutoff entities are exposed only on E v2; A, E v3 and unverified D omit them entirely. A failure of optional E v2 cutoff reads cannot block power control. Live checks found support on E v2, but read exceptions on the installed A and E v3 v150 devices. HBC configurations that target the retired `charge_to_soc` entity need updating.

Options match HBC exactly: disable/enable; manual/anti-feed/ai; stop/charge/discharge. Remaining capacity is capacity × SoC / 100 in kWh. Power retains the reference's signed convention.

Keep HBC's own strategy/configuration helpers; this integration provides the device entities, not the Node-RED strategy engine. Current HBC Full control enables RS485 directly. In HA Managed mode, the retained RS485 goal determines authority: work mode is never written while RS485 is enabled. With RS485 disabled, the integration asserts work mode and retains external-control goals for the next enable. This avoids fighting firmware where the two modes interfere.

Changing the battery number through Reconfigure updates default IDs. Explicit manual renames are preserved and listed in a repair notice; those are exceptions to HBC compatibility. IDs and history remain attached to the same physical identity. Do not install the core and custom marstek implementations simultaneously.

## Fault tolerance

Live values and observed control registers poll every 10 seconds; slow values and schedules every 60 seconds. Individual failures preserve the last successful values. After 180 seconds without a successful component update, its measurement and Battery Managed control entities become unavailable; other components stay available. HA Managed controls continue showing retained goals and expose observation freshness separately. Options allow 120–3600 seconds.

The independent freshness timer runs during outages. A reconnect never fabricates zero power or zero energy. In Battery Managed mode, failed immediate readback is an action error and writes are not replayed. In HA Managed mode, successful services mean the goal was validated and saved; application is asynchronous and may remain pending.

The default is 160 ms request spacing. Options adjust request spacing on all supported versions. Home Assistant 2026.9 uses the transport default timeout (10 seconds); custom timeout tuning is available with modbus-connection 4.12.1 or newer. On those versions, core shares the connection and honors its largest timeout requirement. Timing and per-component ages/errors are included in diagnostics without MAC addresses, hostnames or raw identity data.

## Controls and schedules

The supported HBC power controls are enabled; force-charge-to-SoC is omitted. Additional schedules, cell diagnostics and restart are disabled by default. Enable individual entities in Settings if needed.

Schedules expose clock-time entities, a signed power/mode number, enable switch and seven weekday switches. Weekday edits preserve unrelated bits. Forced settings require RS485 to be enabled explicitly. Restart sends one explicit command. Factory reset is not exposed.

Unresolved register interpretations and firmware caveats are listed in [register uncertainties](docs/register-uncertainties.md).

## Development

The project includes development scripts, tests, and HACS/hassfest workflows. Adapted integration_blueprint files retain their MIT attribution; the device library retains its Apache-2.0 notice. Home Battery Control is a separate GPL-3.0 project; this integration follows its entity contract without including its code.

~~~sh
./scripts/setup stable
./scripts/check stable
~~~

From a fresh checkout, run `./scripts/setup stable` and `./scripts/check stable`. The `development` baseline is also available. Setup downloads pinned Home Assistant Core into the ignored `.test-core/` directory. The checked-in `dev/home-assistant-core/` is only this integration’s Core overlay. Run `python scripts/sync.py --check` to verify generated code; `python scripts/sync.py` regenerates it from checked-in `dev/` sources.

The sync command copies the canonical Core overlay and library into the HACS package, converts imports and manifest metadata, and writes checksums. Edit the source under `dev/` and regenerate the vendored copy; do not edit the copy by hand.

See [Contributing](CONTRIBUTING.md) for the pinned test matrix and [HACS publication](docs/publishing.md) for custom-repository and default-listing gates.

See [hardware validation](docs/hardware-validation.md) and [validation results](docs/validation.md).

## Control register management

The selector beside the battery model offers **HA Managed Control Registers**
(default, will overwrite battery registers) and **Battery Managed Control Registers**
(a readback-based behavior). It can be changed through Reconfigure.

HA Managed owns eight primary controls: RS485 mode, work mode, backup function,
forced direction, forced charge/discharge powers and maximum charge/discharge
powers. E v2 also has optional charge/discharge cutoff goals. Schedules and restart
retain their existing behavior.
The first activation snapshots validated battery readings, including RS485 enable;
no enforcement starts until that snapshot is complete. Missing or invalid values
remain unknown until a valid observation or an explicit request supplies them.
Thereafter battery readings never replace retained goals.

Goals are saved before a service returns and survive Home Assistant restarts,
integration reloads and device reconnects. Control entities remain available during
outages; their `observed_value`, `observed_fresh` and `control_status` attributes
separate battery observations from requested goals. `pending` describes a goal
awaiting fresh matching readback; `deferred` describes a goal suppressed by the
current RS485 branch. Matching readback does not prove physical execution.
Diagnostics include ownership, goals, status, write attempts and transport errors.

Each supported control also has an enabled diagnostic `sensor` ending in
`_readback`, exposing battery observations with the same units or option labels.
These sensors use existing polling and become unavailable when their source is
stale. Enabled diagnostic binary sensors ending in `_in_sync`, plus
`binary_sensor.marstek_mN_controls_in_sync`, compare fresh observations directly
with active retained goals: on for a match, off for a mismatch, unavailable when
required observations or goals are missing. Deferred controls are excluded from
the aggregate and their individual sync sensors are unavailable. Sync sensors
are also unavailable in Battery Managed mode, which has no retained goal state.
Matching registers do not prove physical execution.


When RS485 is enabled, HA repairs drift at approximately the 10-second polling
cadence and reasserts active goals every 60 seconds even if readback matches.
When RS485 is disabled, HA asserts disable and work mode; other goals are stored
without being written. Authority writes allow five seconds for firmware settling;
powers and limits precede forced direction. Failed writes retain intent and retry
with 10/20/40/60-second transport backoff. Commands are serialized and superseded
requests are coalesced. Battery Managed continues requiring immediate readback.

Changing management mode cancels enforcement. Returning to HA Managed starts a
fresh snapshot rather than reviving goals from the previous HA Managed session.
During rollout, disable external controllability watchdogs before checking the
integration's enforcement over several heartbeat cycles. Existing automations
that expect controls to report battery state should use the observation attributes
or select Battery Managed mode. Connectivity watchdogs are a separate concern.

## Releases

Version 0.1.0 is the initial preview. HACS installs `custom_components/marstek` from the selected published release, or from the default branch when no release is available. The generated ZIP is for manual installation.

## Venus E 2.0 through Elfin or LilyGO

Select model `e_v2`, one pack, and the **gateway's** IP address and TCP port.
The gateway must accept Modbus TCP (MBAP framing) and translate it to Modbus RTU
on the battery's RS485 port. A transparent serial TCP tunnel is not supported.
An Elfin EW11/EW11B can provide this translation. The [sanitized LilyGO T-CAN485 ESPHome example](examples/lilygo-t-can485-modbus-bridge.yaml) runs a Modbus TCP-to-RTU gateway and pins its external bridge component. Fill in its private secrets before flashing. MQTT-only or raw serial bridge firmware does not provide this endpoint.

For the LilyGO example, create an untracked `secrets.yaml` beside your copy of the YAML with `wifi_ssid`, `wifi_password`, `marstek_bridge_api_key`, `marstek_bridge_web_user`, and `marstek_bridge_web_password`. Generate the API key with `openssl rand -base64 32`; use a unique web password. The example disables web-interface OTA uploads while keeping the local diagnostics page. It omits a fallback access point, so changing Wi-Fi credentials after flashing requires a reachable native OTA connection or serial access. `./scripts/check_esphome.py` validates it with disposable test secrets through the normal check command.

Configure the serial side for **115200 baud, 8 data bits, no parity, 1 stop bit**,
and use the battery's unit address (normally 1). On Elfin, choose serial protocol
**Modbus**, half duplex, and network **TCP Server**, normally port 502, routed to
UART. Match the configured port in this integration. See the
[Elfin setup reference](https://github.com/WargamingPlayer/HA-Marstek-Venus-E-Modbus#elfin-ew11b)
for adapter settings. Use the wiring documentation for your exact battery and
adapter revision.

The E 2.0 profile reads identity at 30402, battery data at 32100–32105 and AC
data at 32200–32204, including signed 32-bit power. It exposes the HBC controls
and six schedules. Per-cell values and pack cycle counts are omitted because
the legacy reference does not establish them. The HBC work-mode label `ai`
retains code 2, called `trade_mode` in the legacy reference; availability depends
on firmware. Cell temperature scaling follows the pinned map and needs checking
on older BMS firmware. The author has used E 2.0 on hardware for about a week; the exact behavior remains firmware-dependent.

The default is 160 ms request spacing; increase spacing if the gateway is slow. Custom timeout tuning is also available
with modbus-connection 4.12.1 or newer. A read-only check from the library checkout is:

~~~sh
./.venv/stable/bin/python dev/marstek-modbus/script/query.py 192.0.2.10 --model e_v2 --unit 1
~~~

If downgrading from a newer Home Assistant runtime with a saved custom request
timeout, open Marstek options and save to clear that unsupported setting. The
integration then uses 2026.9's default timeout; it never replaces Home Assistant's
Modbus dependency or silently changes another integration's connection settings.
