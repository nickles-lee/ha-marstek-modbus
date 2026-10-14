"""Local diagnostics without raw identity or endpoint disclosure."""

from dataclasses import asdict
from time import monotonic

from homeassistant.core import HomeAssistant

from .coordinator import MarstekConfigEntry


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: MarstekConfigEntry
) -> dict[str, object]:
    """Report cached freshness and timing without additional device requests."""
    coordinator = entry.runtime_data.coordinator
    return {
        "controls": coordinator.controls.diagnostics(),
        "model": coordinator.device.model.value,
        "pack_count": coordinator.device.pack_count,
        "stale_timeout": coordinator.stale_timeout,
        "connection_recovery_attempts": coordinator.recovery_attempts,
        "age_seconds": {
            name: round(monotonic() - stamp, 2)
            for name, stamp in coordinator.last_success.items()
        },
        "failures": dict(coordinator.failures),
        "timing": asdict(coordinator.timed.stats),
    }
