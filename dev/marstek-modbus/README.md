# marstek-modbus

Read and control Marstek Venus A, Venus D, Venus E 2.0 and Venus E v3 batteries over Modbus TCP as typed Python objects.

## Supported devices

| Model | Maximum packs | Cells per pack | Setpoint ceiling | PV |
|---|---:|---:|---:|---|
| Venus A | 6 | 13 | 1500 W | Four inputs |
| Venus D | 7 | 16 | 2500 W | Four inputs |
| Venus E 2.0 | 1 | Not exposed | 2500 W | None |
| Venus E v3 | 1 | 16 | 2500 W | None |

The author reports about a week of real-world use on Venus A, E 2.0, and E v3. Venus D has not been hardware-tested because the author does not own one. Remaining firmware questions are listed in [register uncertainties](../../docs/register-uncertainties.md). Venus E 2.0 uses the separate `e_v2` legacy profile; E v1 is not advertised as supported.

## Usage

~~~python
import asyncio
from modbus_connection import ModbusTcpParams
from modbus_connection.tmodbus import ModbusConnection
from marstek_modbus import MarstekBattery, Model


async def main():
    connection = ModbusConnection(ModbusTcpParams(host="192.0.2.10", port=502))
    unit = connection.for_unit(1)
    unit.set_message_spacing(0.16)
    battery = MarstekBattery(unit, Model.E_V3)
    try:
        report = await battery.async_update()
        print(battery.battery.battery_state_of_charge)
        print(battery.ac.ac_power)
        print(report.failed)
    finally:
        await connection.close()


asyncio.run(main())
~~~

The caller owns the connection, endpoint, timeout and polling policy. The device receives only a ModbusUnit. Use a native TCP endpoint or a gateway translating Modbus TCP into RS485. Raw RTU frames over a TCP socket are a different transport and are not selected by the query script.

## Components and updates

The components mapping names typed subsystem objects. Read identity, battery, ac, pack_1, schedule_1, and the remaining components as attributes or through this mapping.

- async_update_readings(): live measurements and controls.
- async_update_settings(): slower counters, schedules and diagnostics.
- async_update(): both groups.
- async_read_raw(): known registers, without update notifications.
- async_identify(): ASCII MAC and name, without writing anything.

Each update returns an UpdateReport. Successful components notify once at the end of the poll. Failed components retain their previous complete observation. A dead link stops the poll and records unattempted components as failed while preserving earlier successes. One transient timeout is retried if other components answered; a timeout before any answer ends that poll. Setup errors propagate and can be retried by the caller.

Reads use direct addresses, at most 32 words and no undocumented gaps. Packs are separate components at offsets of 100 decimal words. Set pack_count to the installed population; absent packs are not probed.

## Writes

~~~python
from marstek_modbus import RS485Mode, ForcedMode

await battery.async_write("rs485_control_mode", "rs485_control_mode", RS485Mode.ENABLE)
await battery.async_write("forced", "forcible_charge_power", 800)
await battery.async_write("forced", "forcible_charge_discharge", ForcedMode.CHARGE)
await battery.async_set_weekday(1, 0, True)  # Monday, schedule 1
~~~

The `async_write()` and schedule methods serialize operations and confirm settings by readback. Failed or mismatched readback raises ModbusError; the device never invents success or replays an uncertain write. Forced settings require confirmed RS485 enablement. Low-level component write() validates and encodes a field; callers using it must provide serialization and refresh.

For a controller that retains authoritative goals, `async_write_control(component,
field, value, is_current=...)` validates and serializes a primary-control write
without immediate readback or a battery-reported RS485 precondition. Its predicate
is checked inside the device lock: superseded goals return `False` without writing.
An acknowledged write returns `True` but never alters cached observations. The
caller must govern RS485 authority, settling, persistence, retries and observation
refresh; this method cannot write schedules. `validate_write()` on a component
provides the same validation without I/O. The HA integration uses this path only
in HA Managed mode.

Schedule times are HHMM. Schedule mode is -1 for self-consumption, positive 100..model maximum for charge, or negative for discharge. Day masks use Monday bit 0 through Sunday bit 6. Weekday writes preserve other bits.

async_restart() sends a restart once when explicitly called. Polling and connection recovery never write settings.

## Checking a real battery

~~~sh
uv sync
uv run script/query.py 192.0.2.10 --model e_v3 --unit 1
uv run script/query.py 192.0.2.11 --model d --packs 2 --raw
~~~

The query is read-only. Raw output includes identifying data; remove MAC/name/network information before sharing it. It prints request timing, decoded components and failures. Exit code 2 means a partial poll.

## Timing and link tuning

Start with 160 ms between requests. With modbus-connection 4.10.0, the caller's connection timeout applies. Per-unit require_timeout() and require_connect_delay() tuning require 4.12.1 or newer; shared connections then honor the largest unit requirement.

TimedUnit records latency and errors. LinkTuner requires modbus-connection 4.12.1 or newer and is available for callers explicitly choosing adaptive spacing/timeout/connect-delay behavior, following the Sofar reference; it is not automatically enabled. Persist LinkTuning state if using it.

## Development

~~~sh
uv sync
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
uv build
~~~

From the repository root, `./scripts/setup stable` and `./scripts/check stable` run the pinned verification suite. The HACS integration vendors this library; a separate PyPI release is not needed for HACS.

## Evidence and attribution

See [research notes](docs/register-research.md), [source revisions](docs/sources.json), and [register uncertainties](../../docs/register-uncertainties.md). Hardware use on three models does not verify every field or firmware version.

Component architecture, timing utilities and CI/release scaffolding derive from [darkrain-nl/sofar-modbus](https://github.com/darkrain-nl/sofar-modbus), Apache-2.0. Protocol facts are cross-checked against the [Fonske native TCP map](https://github.com/fonske/MarstekVenusV3-modbus-TCP-IP), [Fonske RS485 map](https://github.com/fonske/MarstekVenus-LilygoRS485), [Duravolt protocol document](https://duravolt.nl/wp-content/uploads/Duravolt-Plug-in-Battery-Modbus.pdf), and device observations described in the research notes.

See [validation results](docs/validation.md) for the simulated checks and hardware-validation status.

## Venus E 2.0 through Elfin or LilyGO

Select model `e_v2`, one pack, and the **gateway's** IP address and TCP port.
The gateway must accept Modbus TCP (MBAP framing) and translate it to Modbus RTU
on the battery's RS485 port. A transparent serial TCP tunnel is not supported.
An Elfin EW11/EW11B can provide this translation. A LilyGO with an RS485
transceiver works when its firmware implements the same TCP-to-RTU gateway;
MQTT-only or raw serial bridge firmware does not provide this endpoint.

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
on older BMS firmware. The author has used E 2.0 on hardware for about a week; behavior can vary by firmware.

Start with 160 ms request spacing; increase spacing or timeout in options if the
gateway is slow. A read-only check from the library checkout is:

~~~sh
python script/query.py 192.0.2.10 --model e_v2 --unit 1
~~~

The minimum transport dependency is modbus-connection 4.10.0, matching Home
Assistant 2026.9. Tests also cover 4.12.1.
