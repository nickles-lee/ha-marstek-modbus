"""Marstek sensor entities."""

from typing import Any

from homeassistant.components.sensor import SensorEntity
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
        MarstekSensor(entry, spec)
        for spec in descriptions(device.model, device.pack_count)
        if spec.platform == "sensor"
    )


class MarstekSensor(MarstekEntity, SensorEntity):
    """Marstek sensor entity."""

    def __init__(self, entry: MarstekConfigEntry, spec: Description) -> None:
        """Initialize platform metadata."""
        super().__init__(entry, spec)
        self._attr_native_unit_of_measurement = spec.unit
        self._attr_device_class = spec.device_class
        self._attr_state_class = spec.state_class

    @property
    def native_value(self) -> Any:
        """Return the last successfully decoded observation."""
        return self.value
