"""Common entity identity, freshness and value conversion."""

from typing import Any

from modbus_connection import ModbusError

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from marstek_modbus import Model

from .const import CONF_SLOT, DOMAIN
from .coordinator import MarstekConfigEntry, MarstekCoordinator
from .descriptions import INVERTER_STATES, OPTIONS, Description


class MarstekEntity(CoordinatorEntity[MarstekCoordinator]):
    """An entity whose availability depends on its own source freshness."""

    _attr_has_entity_name = True

    def __init__(self, entry: MarstekConfigEntry, spec: Description) -> None:
        """Bind immutable identity and a canonical initial entity ID."""
        super().__init__(entry.runtime_data.coordinator)
        self.spec = spec
        self._attr_unique_id = f"{entry.unique_id}_{spec.key}"
        self._attr_translation_key = spec.key
        self.entity_id = f"{spec.platform}.marstek_m{entry.data[CONF_SLOT]}_{spec.key}"
        self._attr_entity_registry_enabled_default = spec.enabled
        if spec.diagnostic:
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
        elif spec.component.startswith("schedule_"):
            self._attr_entity_category = EntityCategory.CONFIG
        model_label = self.coordinator.device.model.value.upper().replace("_", " ")
        self._attr_device_info = {
            "identifiers": {(DOMAIN, str(entry.unique_id))},
            "manufacturer": "Marstek",
            "model": f"Venus {model_label}",
            "name": f"M{entry.data[CONF_SLOT]}",
        }

    @property
    def available(self) -> bool:
        """An isolated coordinator failure does not invalidate recent data."""
        if self.spec.sync_for or self.spec.key == "controls_in_sync":
            return self.coordinator.controls.in_sync(self.spec.sync_for) is not None
        if self.coordinator.controls.owns(self.spec):
            return (
                self.spec.component != "cutoffs"
                or self.spec.key in self.coordinator.controls.goals
            )
        return self.coordinator.fresh(self.spec.sources)

    @property
    def value(self) -> Any:
        """Return raw or derived values without manufacturing zeros."""
        if self.coordinator.controls.owns(self.spec):
            return self.coordinator.controls.goals.get(self.spec.key)
        if self.spec.readback_for:
            observed = self.coordinator.controls.observed(self.spec.readback_for)
            if self.spec.readback_for in OPTIONS:
                return next(
                    (
                        label
                        for label, raw in OPTIONS[self.spec.readback_for].items()
                        if raw == observed
                    ),
                    None,
                )
            return observed
        device = self.coordinator.device
        component = device.components[self.spec.component]
        if self.spec.field:
            return getattr(component, self.spec.field)

        def val(name: str) -> Any:
            return getattr(component, name, None)

        key = self.spec.key
        if key == "inverter_state":
            states = INVERTER_STATES
            if device.model is Model.E_V2:
                states = {**states, 4: "Backup Mode", 5: "OTA Upgrade", 6: "Bypass"}
            return states.get(val("inverter_state_number"))
        if key in ("battery_remaining_capacity", "stored_energy"):
            soc, cap = val("battery_state_of_charge"), val("battery_total_energy")
            return None if soc is None or cap is None else round(soc * cap / 100, 2)
        if key == "ac_offgrid_current":
            voltage, power = val("ac_offgrid_voltage"), val("ac_offgrid_power")
            return None if not voltage or power is None else round(power / voltage, 3)
        if key == "solar_power_total":
            powers = [val(f"mppt{i}_power") for i in range(1, 5)]
            return None if any(v is None for v in powers) else sum(powers)
        if key == "firmware_version":
            middle = "software_version" if device.model is Model.E_V2 else "vms_version"
            values = [val(k) for k in ("ems_version", middle, "bms_version")]
            return (
                None
                if any(v is None for v in values)
                else ".".join(str(v) for v in values)
            )
        if key in (
            "round_trip_efficiency_total",
            "round_trip_efficiency_monthly",
        ):
            prefix = "total_monthly" if key.endswith("monthly") else "total"
            charge, discharge = (
                val(f"{prefix}_charging_energy"),
                val(f"{prefix}_discharging_energy"),
            )
            if charge is None or discharge is None:
                return None
            return None if charge <= 0 else round(discharge / charge * 100, 2)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Expose observations separately from authoritative control goals."""
        controls = self.coordinator.controls
        if not controls.owns(self.spec):
            return None
        observed = controls.observed(self.spec.key)
        if self.spec.key in OPTIONS:
            observed = next(
                (
                    label
                    for label, raw in OPTIONS[self.spec.key].items()
                    if raw == observed
                ),
                None,
            )
        return {
            "observed_value": observed,
            "observed_fresh": self.coordinator.fresh(self.spec.sources),
            "control_status": controls.status(self.spec.key),
        }

    async def write(self, value: Any) -> None:
        """Translate transport and validation failures to action errors."""
        try:
            await self.coordinator.write(self.spec.component, self.spec.field, value)
        except (ModbusError, ValueError) as err:
            raise HomeAssistantError(str(err)) from err
