"""Marstek binary_sensor entities."""

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import MarstekConfigEntry
from .descriptions import descriptions
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
        MarstekBinarySensor(entry, spec)
        for spec in descriptions(device.model, device.pack_count)
        if spec.platform == "binary_sensor"
    )


class MarstekBinarySensor(MarstekEntity, BinarySensorEntity):
    """Marstek binary_sensor entity."""

    @property
    def available(self) -> bool:
        """Connection diagnostics remain visible throughout an outage."""
        return True if self.spec.key == "connection" else super().available

    @property
    def is_on(self) -> bool | None:
        """Return connection freshness or a protocol boolean."""
        if self.spec.sync_for or self.spec.key == "controls_in_sync":
            return self.coordinator.controls.in_sync(self.spec.sync_for)
        if self.spec.key == "connection":
            return self.coordinator.fresh(("state",))
        return self.value
