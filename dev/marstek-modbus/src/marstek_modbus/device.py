"""A caller-owned Modbus unit mapped to a Marstek Venus battery."""

import asyncio
import re
from collections.abc import Callable, Iterable
from typing import Any, cast

from modbus_connection import (
    ModbusConnectionError,
    ModbusError,
    ModbusTimeoutError,
    ModbusUnit,
)

from .components import (
    A_COMPONENTS,
    D_COMPONENTS,
    E_V2_COMPONENTS,
    E_V3_COMPONENTS,
    AAc,
    ABattery,
    AIdentity,
    EV2CellExtrema,
)
from .enums import Capability, Model, RS485Mode
from .model import MarstekComponent, ReadbackError, UpdateReport
from .parts import CellExtrema, DPack, Pack, Schedule

Raw = dict[str, dict[int, int | bool]]


class MarstekBattery:
    """Typed components, serialized operations, and independent update reports."""

    def __init__(self, unit: ModbusUnit, model: Model, *, pack_count: int = 1) -> None:
        """Build only the selected model and configured pack population."""
        self.modbus_unit = unit
        self._setup_done = False
        self.model = Model(model)
        if not 1 <= pack_count <= self.model.max_packs:
            raise ValueError("Invalid pack count for this model")
        self.pack_count = pack_count
        self.capabilities = Capability.BATTERY | Capability.BACKUP
        if self.model in (Model.A, Model.D):
            self.capabilities |= Capability.PV | Capability.EXPANDABLE
        classes = {
            Model.A: A_COMPONENTS,
            Model.D: D_COMPONENTS,
            Model.E_V2: E_V2_COMPONENTS,
            Model.E_V3: E_V3_COMPONENTS,
        }[self.model]
        self.components: dict[str, MarstekComponent] = {}
        for name, cls in classes.items():
            self.components[name] = cls(unit)
        for i in range(1, 1 if self.model is Model.E_V2 else pack_count + 1):
            pack = (DPack if self.model is Model.D else Pack)(
                unit, base_offset=(i - 1) * 100
            )
            if self.model is Model.A:
                pack.restrict_fields(
                    [
                        k
                        for k in pack.declared_fields
                        if k not in {f"cell_{n}_voltage" for n in (14, 15, 16)}
                    ]
                )
            self.components[f"pack_{i}"] = pack
        for i in range(1, 7):
            self.components[f"schedule_{i}"] = Schedule(unit, base_offset=(i - 1) * 5)
        self.components["cell_extrema"] = (
            EV2CellExtrema if self.model is Model.E_V2 else CellExtrema
        )(unit)
        for name, component in self.components.items():
            component.power_limit = self.model.max_power
            setattr(self, name, component)
        self.identity = cast(AIdentity, self.components["identity"])
        self.battery = cast(ABattery, self.components["battery"])
        self.ac = cast(AAc, self.components["ac"])
        self.settings_components = tuple(
            n
            for n in self.components
            if n.startswith("schedule_")
            or n in ("firmware", "energy", "network", "cutoffs")
        )
        self.readings_components = tuple(
            n
            for n in self.components
            if n not in self.settings_components and n != "identity"
        )
        self._lock = asyncio.Lock()
        self.last_report = UpdateReport()

    @property
    def mac_address(self) -> str:
        """Validated stable identity encoded as twelve ASCII hex digits."""
        raw = getattr(self.identity, "ble_mac_address", None)
        if (
            not isinstance(raw, str)
            or not re.fullmatch(r"[0-9a-fA-F]{12}", raw)
            or raw.lower() in ("0" * 12, "f" * 12)
        ):
            raise ValueError("Device returned an invalid MAC identity")
        return ":".join(raw[i : i + 2] for i in range(0, 12, 2)).lower()

    async def _async_setup(self) -> None:
        await self.identity.async_update()
        _ = self.mac_address

    async def async_ensure_setup(self) -> None:
        """Cache identity only after setup succeeds; failed setup remains retryable."""
        if not self._setup_done:
            await self._async_setup()
            self._setup_done = True

    async def async_identify(self) -> str:
        """Validate identity without reading settings or writing anything."""
        async with self._lock:
            await self.async_ensure_setup()
            return self.mac_address

    async def _poll(self, names: Iterable[str]) -> UpdateReport:
        async with self._lock:
            await self.async_ensure_setup()
            report = UpdateReport()
            ordered = tuple(names)
            for index, name in enumerate(ordered):
                try:
                    await self.components[name].async_update(notify=False)
                except (ModbusConnectionError, ModbusTimeoutError) as err:
                    report.failed[name] = err
                    if isinstance(err, ModbusConnectionError) or not report.updated:
                        for skipped in ordered[index + 1 :]:
                            report.failed[skipped] = err
                        break
                except ModbusError as err:
                    report.failed[name] = err
                else:
                    report.updated.add(name)
            # A bounded retry of transient component failures only on a live link.
            if report.updated and not any(
                isinstance(e, ModbusConnectionError) for e in report.failed.values()
            ):
                for name, failure in tuple(report.failed.items()):
                    if not isinstance(failure, ModbusTimeoutError):
                        continue
                    try:
                        await self.components[name].async_update(notify=False)
                    except ModbusError as retry_error:
                        report.failed[name] = retry_error
                        if isinstance(retry_error, ModbusConnectionError):
                            break
                    else:
                        report.updated.add(name)
                        del report.failed[name]
            self.last_report = report
            for name in report.updated:
                self.components[name].notify()
            return report

    async def async_update_readings(self) -> UpdateReport:
        """Refresh live readings and controls."""
        return await self._poll(self.readings_components)

    async def async_update_settings(self) -> UpdateReport:
        """Refresh slow measurements, schedules and diagnostics."""
        return await self._poll(self.settings_components)

    async def async_update(self) -> UpdateReport:
        """Refresh both groups in one serialized poll."""
        return await self._poll((*self.readings_components, *self.settings_components))

    async def async_read_raw(self, names: Iterable[str] | None = None) -> Raw:
        """Read bounded, known registers without listener notification."""
        async with self._lock:
            await self.async_ensure_setup()
            raw: Raw = {}
            for name in names if names is not None else self.components:
                for space, values in (
                    await self.components[name].async_read_raw(notify=False)
                ).items():
                    raw.setdefault(space, {}).update(values)
            return raw

    async def async_write(self, component: str, field: str, value: Any) -> None:
        """Write once, then confirm by reading; never optimistically alter state."""
        async with self._lock:
            target = self.components[component]
            if component == "forced":
                mode = self.components["rs485_control_mode"]
                await mode.async_update()
                mode_field = "rs485_control_mode"
                if getattr(mode, mode_field) != RS485Mode.ENABLE:
                    raise ValueError(
                        "Enable RS485 control before writing forced settings"
                    )
            await target.write(field, value)
            await target.async_update()
            if getattr(target, field) != value:
                raise ReadbackError(
                    f"{component}.{field}: requested setting was not confirmed"
                )

    async def async_write_control(
        self,
        component: str,
        field: str,
        value: Any,
        *,
        is_current: Callable[[], bool],
    ) -> bool:
        """Apply caller-owned control intent without trusting firmware readback.

        The caller owns RS485 authority and retry policy. Recheck intent after
        acquiring the device lock so queued commands cannot replay stale goals.
        Observations are updated only by subsequent polling.
        """
        if component not in {
            "rs485_control_mode",
            "user_work_mode",
            "forced",
            "limits",
            "cutoffs",
            "backup_function",
        }:
            raise ValueError("Not a managed control component")
        async with self._lock:
            if not is_current():
                return False
            await self.components[component].write(field, value)
            return True

    async def async_set_weekday(self, schedule: int, day: int, enabled: bool) -> None:
        """Read-modify-write one weekday while retaining all other bits."""
        if not 1 <= schedule <= 6 or not 0 <= day <= 6:
            raise ValueError("Invalid schedule or weekday")
        async with self._lock:
            component = self.components[f"schedule_{schedule}"]
            address = 43100 + (schedule - 1) * 5
            word = (await self.modbus_unit.read_holding_registers(address, 1))[0]
            updated = word | (1 << day) if enabled else word & ~(1 << day)
            await self.modbus_unit.write_register(address, updated)
            await component.async_update()
            days_field = "days"
            if int(getattr(component, days_field)) != updated:
                raise ReadbackError("Weekday write was not confirmed")

    async def async_restart(self) -> None:
        """Send the documented restart command once, only on explicit request."""
        async with self._lock:
            await self.modbus_unit.write_register(41000, 0x55AA)
