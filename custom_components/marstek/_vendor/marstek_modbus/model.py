"""Transactional components and validation shared by the device models."""

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any

from modbus_connection import ModbusError
from modbus_connection.model import Component

__all__ = ["MarstekComponent", "UpdateReport", "ReadbackError", "InvalidResponse"]


@dataclass
class UpdateReport:
    """Successful components and failures from one poll, across library versions."""

    updated: set[str] = field(default_factory=set)
    failed: dict[str, ModbusError] = field(default_factory=dict)

    @property
    def complete(self) -> bool:
        """Whether every attempted component refreshed successfully."""
        return not self.failed


class ReadbackError(ModbusError):
    """A write was acknowledged but the requested setting was not confirmed."""


class InvalidResponse(ModbusError):
    """A response could not be decoded as a valid device observation."""


class MarstekComponent(Component):
    """A subsystem with bounded reads and last-successful-value semantics."""

    max_span = 32
    max_gap = 0
    power_limit = 2500

    async def async_update(self, *, notify: bool = True) -> None:
        """Commit all fields together, rolling back malformed or failed reads."""
        previous = self._values.copy()
        try:
            await super().async_update(notify=False)
        except BaseException as err:
            self._values = previous
            # Cached plans refer to the old dictionary.
            self._invalidate_caches()
            if isinstance(err, (ValueError, IndexError, TypeError)):
                raise InvalidResponse(str(err)) from err
            raise
        if notify:
            self.notify()

    async def async_read_raw(
        self, *, notify: bool = True
    ) -> dict[str, dict[int, int | bool]]:
        """Apply the same atomic cache semantics to diagnostic reads."""
        previous = self._values.copy()
        try:
            result = await super().async_read_raw(notify=False)
        except BaseException as err:
            self._values = previous
            self._invalidate_caches()
            if isinstance(err, (ValueError, IndexError, TypeError)):
                raise InvalidResponse(str(err)) from err
            raise
        if notify:
            self.notify()
        return result

    def validate_write(self, field: str, value: Any) -> None:
        """Validate protocol codes and physical bounds without device I/O."""
        resolved = self.resolved_fields.get(field)
        if resolved is None or not resolved.field.writable:
            raise AttributeError(f"Unknown or read-only field: {field}")
        cutoff_ranges = {
            "charging_cutoff_capacity": (80, 100),
            "discharging_cutoff_capacity": (12, 30),
        }
        if field in cutoff_ranges:
            minimum, maximum = cutoff_ranges[field]
            if (
                not isinstance(value, (int, float))
                or not minimum <= value <= maximum
                or abs(value * 10 - round(value * 10)) > 1e-8
            ):
                raise ValueError(
                    f"Cutoff must be between {minimum} and {maximum} percent "
                    "in 0.1 percent steps"
                )
        elif not isinstance(value, (int, float)) or int(value) != value:
            raise ValueError("A whole-number value is required")
        convert = getattr(resolved.field, "convert", None)
        if isinstance(convert, type) and issubclass(convert, IntEnum):
            convert(int(value))
        if field.endswith("power") and not 0 <= value <= self.power_limit:
            raise ValueError(f"Power must be between 0 and {self.power_limit} W")
        if field == "charge_to_soc" and not 10 <= value <= 100:
            raise ValueError("Target SoC must be between 10 and 100 percent")
        if field in ("start", "end"):
            if not 0 <= value <= 2359 or value % 100 > 59:
                raise ValueError("Time must be HHMM with minutes in 00..59")
        if (
            field == "mode"
            and value != -1
            and not 100 <= abs(value) <= self.power_limit
        ):
            raise ValueError(
                "Schedule mode must be -1 or a signed power of at least 100 W"
            )
        if field == "days" and not 0 <= value <= 127:
            raise ValueError("Weekday mask must fit seven bits")
        if field == "enabled" and value not in (0, 1):
            raise ValueError("Enabled must be 0 or 1")

    async def write(self, field: str, value: Any) -> None:
        """Validate before sending a write."""
        self.validate_write(field, value)
        await super().write(field, value)
