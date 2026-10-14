"""Setup, reconfiguration and options for Marstek."""

import asyncio
from importlib.metadata import version
from typing import Any

import probatio as vol
from awesomeversion import AwesomeVersion
from modbus_connection import ModbusError, ModbusTcpParams

from homeassistant.components.modbus import async_get_temporary_unit
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorMode,
)
from marstek_modbus import MarstekBattery, Model

from .const import (
    BATTERY_MANAGED,
    CONF_CONTROL_MANAGEMENT,
    CONF_MODEL,
    CONF_PACKS,
    CONF_SLOT,
    CONF_SPACING,
    CONF_STALE,
    CONF_TIMEOUT,
    CONF_UNIT,
    DEFAULT_SPACING,
    DEFAULT_STALE,
    DOMAIN,
    HA_MANAGED,
)
from .descriptions import descriptions
from .naming import collision, rename_slot


def _integer(low: int, high: int) -> Any:
    return vol.All(vol.Coerce(int), vol.Range(min=low, max=high))


class _IntegerSelector(NumberSelector):
    """Render an explicit numeric control and store only whole numbers."""

    def __call__(self, data: Any) -> int:
        value = super().__call__(data)
        if not value.is_integer():
            raise vol.Invalid("A whole number is required")
        return int(value)


class _PackSelector(_IntegerSelector):
    """Show expandable pack counts only for the A and D profiles."""

    def serialize(self) -> dict[str, Any]:
        return {
            **super().serialize(),
            "visible": {"field": CONF_MODEL, "operator": "in", "value": ["a", "d"]},
        }


def _schema(slot: int = 1) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_HOST): str,
            vol.Required(CONF_PORT, default=502): _integer(1, 65535),
            vol.Required(CONF_UNIT, default=1): _IntegerSelector(
                {"min": 1, "max": 247, "step": 1, "mode": NumberSelectorMode.BOX}
            ),
            vol.Required(CONF_MODEL, default="e_v3"): SelectSelector(
                {
                    "mode": SelectSelectorMode.LIST,
                    "options": [
                        {"value": "a", "label": "Venus A"},
                        {"value": "d", "label": "Venus D"},
                        {"value": "e_v2", "label": "Venus E 2.0"},
                        {"value": "e_v3", "label": "Venus E 3.0"},
                    ],
                }
            ),
            vol.Required(CONF_CONTROL_MANAGEMENT, default=HA_MANAGED): SelectSelector(
                {
                    "mode": SelectSelectorMode.LIST,
                    "options": [
                        {"value": HA_MANAGED, "label": "HA Managed Control Registers"},
                        {
                            "value": BATTERY_MANAGED,
                            "label": "Battery Managed Control Registers",
                        },
                    ],
                }
            ),
            vol.Optional(CONF_PACKS, default=1): _PackSelector(
                {"min": 1, "max": 6, "step": 1, "mode": NumberSelectorMode.SLIDER}
            ),
            vol.Required(CONF_SLOT, default=slot): _integer(1, 999),
        }
    )


async def probe(hass: Any, data: dict[str, Any]) -> str:
    """Retry identity reads without ever writing a register."""
    params = ModbusTcpParams(host=data[CONF_HOST], port=data[CONF_PORT])
    async with async_get_temporary_unit(hass, params, data[CONF_UNIT]) as unit:
        unit.set_message_spacing(DEFAULT_SPACING / 1000)
        for attempt in range(3):
            try:
                return await MarstekBattery(
                    unit, Model(data[CONF_MODEL]), pack_count=data[CONF_PACKS]
                ).async_identify()
            except ModbusError:
                if attempt == 2:
                    raise
                await asyncio.sleep(0.2)
    raise AssertionError("Unreachable")


class MarstekConfigFlow(ConfigFlow, domain=DOMAIN):
    """Configure one physical battery."""

    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Expose freshness and transport tuning without replacing dependencies."""
        return MarstekOptionsFlow()

    def _next_slot(self) -> int:
        slot = 1
        while collision(self.hass, {CONF_SLOT: slot}, descriptions(Model.D, 7)):
            slot += 1
        return slot

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Set up a battery with the first available HBC slot."""
        return await self._form(user_input, False)

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Edit endpoint, pack count and HBC slot with identity validation."""
        return await self._form(user_input, True)

    async def _form(
        self, data: dict[str, Any] | None, reconfigure: bool
    ) -> ConfigFlowResult:
        errors = {}
        entry = self._get_reconfigure_entry() if reconfigure else None
        if data is not None:
            data = dict(data)
            data.setdefault(
                CONF_CONTROL_MANAGEMENT,
                entry.data.get(CONF_CONTROL_MANAGEMENT, HA_MANAGED)
                if entry
                else HA_MANAGED,
            )
            model = Model(data[CONF_MODEL])
            # Hidden fields may retain a previous A/D selection in the browser.
            if model in (Model.E_V2, Model.E_V3):
                data[CONF_PACKS] = 1
            else:
                data.setdefault(CONF_PACKS, 1)
            if not 1 <= data[CONF_PACKS] <= min(6, model.max_packs):
                errors[CONF_PACKS] = "invalid_pack_count"
            elif collision(
                self.hass,
                data,
                descriptions(model, data[CONF_PACKS]),
                entry.entry_id if entry else None,
            ):
                errors[CONF_SLOT] = "slot_in_use"
            else:
                try:
                    mac = await probe(self.hass, data)
                except ValueError:
                    errors["base"] = "invalid_identity"
                except ModbusError, HomeAssistantError:
                    errors["base"] = "cannot_connect"
                else:
                    await self.async_set_unique_id(mac)
                    if entry:
                        self._abort_if_unique_id_mismatch()
                        # No awaits between collision validation and registry mutation.
                        if collision(
                            self.hass,
                            data,
                            descriptions(model, data[CONF_PACKS]),
                            entry.entry_id,
                        ):
                            errors[CONF_SLOT] = "slot_in_use"
                        else:
                            if data[CONF_SLOT] != entry.data[CONF_SLOT]:
                                rename_slot(
                                    self.hass,
                                    entry.entry_id,
                                    entry.data[CONF_SLOT],
                                    data[CONF_SLOT],
                                )
                            return self.async_update_reload_and_abort(
                                entry, data_updates=data
                            )
                    else:
                        self._abort_if_unique_id_configured()
                        if collision(
                            self.hass, data, descriptions(model, data[CONF_PACKS])
                        ):
                            errors[CONF_SLOT] = "slot_in_use"
                        else:
                            return self.async_create_entry(
                                title=f"M{data[CONF_SLOT]}", data=data
                            )
        schema = _schema(entry.data[CONF_SLOT] if entry else self._next_slot())
        if data or entry:
            schema = self.add_suggested_values_to_schema(schema, data or entry.data)
        return self.async_show_form(
            step_id="reconfigure" if entry else "user",
            data_schema=schema,
            errors=errors,
        )


class MarstekOptionsFlow(OptionsFlow):
    """Polling freshness and per-unit connection requirements."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Save validated tuning options."""
        supports_timeout = AwesomeVersion(
            version("modbus-connection")
        ) >= AwesomeVersion("4.12.1")
        if user_input is not None:
            # Saving options on 2026.9 also clears a timeout from a newer runtime.
            data = dict(user_input)
            if not supports_timeout:
                data.pop(CONF_TIMEOUT, None)
            return self.async_create_entry(data=data)
        options = self.config_entry.options
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_STALE, default=options.get(CONF_STALE, DEFAULT_STALE)
                    ): _integer(120, 3600),
                    vol.Required(
                        CONF_SPACING, default=options.get(CONF_SPACING, DEFAULT_SPACING)
                    ): _integer(0, 1000),
                    **(
                        {
                            vol.Optional(CONF_TIMEOUT): vol.All(
                                vol.Coerce(float), vol.Range(min=1, max=60)
                            )
                        }
                        if supports_timeout
                        else {}
                    ),
                }
            ),
        )
