"""Entity contract and source-to-entity mapping."""

from dataclasses import dataclass
from typing import Any

from homeassistant.helpers.entity import EntityDescription
from marstek_modbus import Model

from .catalog import CATALOG

CONTROL_KEYS = frozenset(
    {
        "rs485_control_mode",
        "user_work_mode",
        "forcible_charge_discharge",
        "forcible_charge_power",
        "forcible_discharge_power",
        "max_charge_power",
        "max_discharge_power",
        # "charge_to_soc",  # Never heartbeat an active SoC-target command.
        "charging_cutoff_capacity",
        "discharging_cutoff_capacity",
        "backup_function",
    }
)

HBC_KEYS = {
    "device_name",
    "battery_state_of_charge",
    "battery_voltage",
    "battery_total_energy",
    "ac_power",
    "battery_power",
    "inverter_state_number",
    "inverter_state",
    "battery_remaining_capacity",
    "max_charge_power",
    "max_discharge_power",
    "forcible_charge_power",
    "forcible_discharge_power",
    # "charge_to_soc",  # Disabled: this activates SoC-target mode.
    "rs485_control_mode",
    "user_work_mode",
    "forcible_charge_discharge",
    "backup_function",
}
OPTIONS = {
    "rs485_control_mode": {"disable": 21947, "enable": 21930},
    "user_work_mode": {"manual": 0, "anti-feed": 1, "ai": 2},
    "forcible_charge_discharge": {"stop": 0, "charge": 1, "discharge": 2},
    "backup_function": {"enable": 0, "disable": 1},
}
INVERTER_STATES = {
    0: "Sleep",
    1: "Standby",
    2: "Charge",
    3: "Discharge",
    4: "Fault",
    5: "Idle",
    6: "AC bypass",
}
DAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")


@dataclass(frozen=True, kw_only=True)
class Description(EntityDescription):
    """A stable interface key and its source component dependencies."""

    key: str
    component: str
    field: str = ""
    platform: str = "sensor"
    unit: str | None = None
    device_class: str | None = None
    state_class: str | None = None
    enabled: bool = False
    diagnostic: bool = False
    min: int = 0
    max: int = 0
    step: float = 1
    readback_for: str | None = None
    sync_for: str | None = None
    dependencies: tuple[str, ...] = ()
    day: int | None = None

    @property
    def sources(self) -> tuple[str, ...]:
        """All components whose freshness this entity requires."""
        return self.dependencies or (self.component,)


def descriptions(model: Model, pack_count: int) -> tuple[Description, ...]:
    """Build model-supported entities, with every HBC field enabled."""
    result = []
    for item in CATALOG[model.value]:
        data: dict[str, Any] = dict(item)
        if data["key"] in HBC_KEYS:
            data["enabled"] = True
        result.append(Description(**data))
    for n in range(1, 1 if model is Model.E_V2 else pack_count + 1):
        group = f"pack_{n}"
        result.extend(
            [
                Description(
                    key=f"battery_soc_{n}",
                    component=group,
                    field="state_of_charge",
                    unit="%",
                    device_class="battery",
                    state_class="measurement",
                ),
                Description(
                    key="battery_cycle_count" if n == 1 else f"battery_{n}_cycle_count",
                    component=group,
                    field="cycle_count",
                    diagnostic=True,
                    enabled=n == 1,
                ),
            ]
        )
        result.extend(
            Description(
                key=f"battery_{n}_cell_{cell}_voltage",
                component=group,
                field=f"cell_{cell}_voltage",
                unit="V",
                device_class="voltage",
                state_class="measurement",
                diagnostic=True,
            )
            for cell in range(1, model.cells + 1)
        )
        if model is Model.D:
            for field, unit, dc in [
                ("voltage", "V", "voltage"),
                ("current", "A", "current"),
                ("max_cell_voltage", "V", "voltage"),
                ("min_cell_voltage", "V", "voltage"),
                ("max_temperature", "°C", "temperature"),
                *[(f"temperature_{i}", "°C", "temperature") for i in range(7)],
                ("charge_status", None, None),
                ("protection_1", None, None),
                ("protection_2", None, None),
                ("bms_version", None, None),
            ]:
                result.append(
                    Description(
                        key=f"battery_{n}_{field}",
                        component=group,
                        field=field,
                        unit=unit,
                        device_class=dc,
                        diagnostic=True,
                    )
                )
    for n in range(1, 7):
        group = f"schedule_{n}"
        result.extend(
            [
                Description(
                    key=f"{group}_start",
                    component=group,
                    field="start",
                    platform="time",
                ),
                Description(
                    key=f"{group}_end", component=group, field="end", platform="time"
                ),
                Description(
                    key=f"{group}_mode",
                    component=group,
                    field="mode",
                    platform="number",
                    min=-model.max_power,
                    max=model.max_power,
                ),
                Description(
                    key=f"{group}_enabled",
                    component=group,
                    field="enabled",
                    platform="switch",
                ),
            ]
        )
        for day, label in enumerate(DAYS):
            result.append(
                Description(
                    key=f"{group}_{label}",
                    component=group,
                    field="days",
                    platform="switch",
                    day=day,
                )
            )
    result.extend(
        Description(
            key=key,
            component="cell_extrema",
            field=key,
            unit="V",
            device_class="voltage",
            state_class="measurement",
        )
        for key in ("max_cell_voltage", "min_cell_voltage")
    )
    virtual = [
        Description(
            key="inverter_state",
            component="state",
            dependencies=("state",),
            enabled=True,
        ),
        Description(
            key="battery_remaining_capacity",
            component="battery",
            dependencies=("battery",),
            unit="kWh",
            device_class="energy_storage",
            state_class="measurement",
            enabled=True,
        ),
        Description(
            key="stored_energy",
            component="battery",
            unit="kWh",
            device_class="energy_storage",
            state_class="measurement",
            dependencies=("battery",),
        ),
        Description(
            key="round_trip_efficiency_total",
            component="energy",
            unit="%",
            enabled=True,
        ),
        Description(key="round_trip_efficiency_monthly", component="energy", unit="%"),
        Description(
            key="ac_offgrid_current",
            component="backup_readings",
            field="ac_offgrid_current" if model is Model.E_V2 else "",
            unit="A",
            device_class="current",
            state_class="measurement",
        ),
        Description(key="firmware_version", component="firmware", diagnostic=True),
        Description(
            key="connection",
            component="state",
            platform="binary_sensor",
            diagnostic=True,
            enabled=True,
        ),
        Description(
            key="restart", component="state", platform="button", diagnostic=True
        ),
    ]
    if model in (Model.A, Model.D):
        virtual.append(
            Description(
                key="solar_power_total",
                component="pv",
                unit="W",
                device_class="power",
                state_class="measurement",
            )
        )
    result.extend(virtual)
    controls = [spec for spec in result if spec.key in CONTROL_KEYS]
    for spec in controls:
        result.extend(
            [
                Description(
                    key=f"{spec.key}_readback",
                    component=spec.component,
                    field=spec.field,
                    unit=spec.unit,
                    dependencies=spec.sources,
                    readback_for=spec.key,
                    diagnostic=True,
                    enabled=True,
                ),
                Description(
                    key=f"{spec.key}_in_sync",
                    component=spec.component,
                    platform="binary_sensor",
                    dependencies=spec.sources,
                    sync_for=spec.key,
                    diagnostic=True,
                    enabled=True,
                ),
            ]
        )
    result.append(
        Description(
            key="controls_in_sync",
            component="state",
            platform="binary_sensor",
            diagnostic=True,
            enabled=True,
        )
    )
    return tuple(result)
