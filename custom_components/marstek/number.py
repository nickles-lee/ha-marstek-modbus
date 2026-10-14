"""Marstek number entities."""

from typing import Any

from homeassistant.components.number import NumberEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import MarstekConfigEntry
from .descriptions import Description, descriptions
from .entity import MarstekEntity

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: MarstekConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add model-supported entities."""
    device = entry.runtime_data.coordinator.device
    async_add_entities(
        MarstekNumber(entry, spec)
        for spec in descriptions(device.model, device.pack_count)
        if spec.platform == "number"
    )


class MarstekNumber(MarstekEntity, NumberEntity):
    """Marstek number entity."""

    def __init__(self, entry: MarstekConfigEntry, spec: Description) -> None:
        """Initialize platform metadata."""
        super().__init__(entry, spec)
        self._attr_native_unit_of_measurement = spec.unit
        self._attr_native_min_value = spec.min
        self._attr_native_max_value = spec.max
        self._attr_native_step = spec.step

    @property
    def native_value(self) -> Any:
        """Return the retained goal or battery-managed readback."""
        return self.value

    async def async_set_native_value(self, value: float) -> None:
        """Request a setpoint using the configured management policy."""
        await self.write(value)
