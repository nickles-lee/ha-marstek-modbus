"""Marstek Venus batteries using the shared Modbus connection."""

from importlib.metadata import version

from awesomeversion import AwesomeVersion
from modbus_connection import ModbusError, ModbusTcpParams

from homeassistant.components.modbus import async_get_unit
from homeassistant.const import CONF_HOST, CONF_PORT, Platform, __version__
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from marstek_modbus import MarstekBattery, Model
from marstek_modbus.tuning import TimedUnit

from .const import (
    CONF_CONTROL_MANAGEMENT,
    CONF_MODEL,
    CONF_PACKS,
    CONF_SLOT,
    CONF_SPACING,
    CONF_TIMEOUT,
    CONF_UNIT,
    DEFAULT_SPACING,
    DOMAIN,
    HA_MANAGED,
    MIN_VERSION,
)
from .coordinator import MarstekConfigEntry, MarstekCoordinator, MarstekRuntimeData
from .descriptions import descriptions
from .naming import collision

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)
PLATFORMS = [
    Platform.SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
    Platform.TIME,
    Platform.BUTTON,
]


async def async_setup_entry(hass: HomeAssistant, entry: MarstekConfigEntry) -> bool:
    """Validate identity, refresh and forward entity platforms."""
    if AwesomeVersion(__version__) < AwesomeVersion(MIN_VERSION) or AwesomeVersion(
        version("modbus-connection")
    ) < AwesomeVersion("4.10.0"):
        raise ConfigEntryError(
            "Marstek requires Home Assistant 2026.9.0 or newer "
            "and modbus-connection 4.10.0 or newer"
        )
    if CONF_CONTROL_MANAGEMENT not in entry.data:
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, CONF_CONTROL_MANAGEMENT: HA_MANAGED}
        )
    slot = entry.data[CONF_SLOT]
    if entry.title in (f"Marstek m{slot}", f"Marstek M{slot}", f"m{slot}"):
        hass.config_entries.async_update_entry(entry, title=f"M{slot}")
    specs = descriptions(Model(entry.data[CONF_MODEL]), entry.data[CONF_PACKS])
    if conflict := collision(hass, entry.data, specs, entry.entry_id):
        raise ConfigEntryError(f"Entity ID collision: {conflict}")
    unit = async_get_unit(
        hass,
        entry,
        ModbusTcpParams(host=entry.data[CONF_HOST], port=entry.data[CONF_PORT]),
        entry.data[CONF_UNIT],
    )
    unit.set_message_spacing(entry.options.get(CONF_SPACING, DEFAULT_SPACING) / 1000)
    timed = TimedUnit(unit)
    try:
        timed.require_timeout(entry.options.get(CONF_TIMEOUT))
    except ValueError as err:
        raise ConfigEntryError(
            "Custom request timeout is unavailable on this Modbus version. "
            "Open Marstek options and save to use the default timeout."
        ) from err
    device = MarstekBattery(
        timed, Model(entry.data[CONF_MODEL]), pack_count=entry.data[CONF_PACKS]
    )
    try:
        mac = await device.async_identify()
    except ModbusError as err:
        raise ConfigEntryNotReady("Cannot read battery identity") from err
    except ValueError as err:
        raise ConfigEntryError(str(err)) from err
    if mac != entry.unique_id:
        raise ConfigEntryError("The endpoint belongs to a different battery")
    coordinator = MarstekCoordinator(hass, entry, device, timed)
    entry.runtime_data = MarstekRuntimeData(coordinator)
    try:
        await coordinator.controls.async_load()
    except (ValueError, TypeError, AttributeError) as err:
        raise ConfigEntryError("Stored control goals are invalid") from err
    except OSError as err:
        raise ConfigEntryNotReady("Cannot load control goals") from err
    for name, component in device.components.items():
        entry.async_on_unload(
            component.add_update_listener(
                lambda n=name: coordinator.component_updated(n)
            )
        )
    await coordinator.async_config_entry_first_refresh()
    coordinator.start_expiry()
    if not entry.data.get("rte_default_applied", False):
        registry = er.async_get(hass)
        entity_id = registry.async_get_entity_id(
            "sensor", DOMAIN, f"{entry.unique_id}_round_trip_efficiency_total"
        )
        if (
            entity_id
            and registry.entities[entity_id].disabled_by
            is er.RegistryEntryDisabler.INTEGRATION
        ):
            registry.async_update_entity(entity_id, disabled_by=None)
        hass.config_entries.async_update_entry(
            entry, data={**entry.data, "rte_default_applied": True}
        )
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(coordinator.controls.stop)
    coordinator.controls.start()
    entry.async_on_unload(entry.add_update_listener(_async_reload))
    return True


async def _async_reload(hass: HomeAssistant, entry: MarstekConfigEntry) -> None:
    """Apply edited polling and connection settings."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: MarstekConfigEntry) -> bool:
    """Release platforms, timers and the shared unit hold."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
