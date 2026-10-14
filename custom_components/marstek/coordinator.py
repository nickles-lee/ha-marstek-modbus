"""Polling and per-component expiry independent of transport success."""

import asyncio
import logging
from dataclasses import dataclass
from datetime import timedelta
from time import monotonic
from typing import Any

from modbus_connection import ModbusConnectionError, ModbusError

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from ._vendor.marstek_modbus import MarstekBattery, UpdateReport
from ._vendor.marstek_modbus.tuning import TimedUnit
from .const import CONF_STALE, DEFAULT_STALE, SCAN_INTERVAL, SLOW_INTERVAL
from .control import ManagedControls

_LOGGER = logging.getLogger(__name__)
RECOVERY_INTERVAL = 90.0
RECOVERY_TIMEOUT = 10.0


class MarstekCoordinator(DataUpdateCoordinator[UpdateReport]):
    """Retain observations through transient failures and expire stale sources."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        device: MarstekBattery,
        timed: TimedUnit,
    ) -> None:
        """Initialize polling state."""
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=entry.title,
            update_interval=timedelta(seconds=SCAN_INTERVAL),
        )
        self.device = device
        self.timed = timed
        self.last_success: dict[str, float] = {"identity": monotonic()}
        self.failures: dict[str, str] = {}
        self._slow_due = 0.0
        self._ever_answered = False
        self._started = monotonic()
        self._last_recovery = self._started
        self._recovery_task: asyncio.Task[None] | None = None
        self._recovery_refresh: asyncio.Task[None] | None = None
        self.recovery_attempts = 0
        self.stale_timeout = entry.options.get(CONF_STALE, DEFAULT_STALE)
        self.controls = ManagedControls(self)

    @callback
    def start_expiry(self) -> None:
        """Wake entities even while requests are stalled or failing."""
        assert self.config_entry is not None
        self.config_entry.async_on_unload(
            async_track_time_interval(self.hass, self._expire, timedelta(seconds=1))
        )

    @callback
    def _expire(self, now: Any) -> None:
        self.async_update_listeners()
        self.controls.request()
        last_response = self.timed.last_response
        if (
            monotonic()
            - (last_response if last_response is not None else self._started)
            > RECOVERY_INTERVAL
            and monotonic() - self._last_recovery >= RECOVERY_INTERVAL
            and (self._recovery_task is None or self._recovery_task.done())
        ):
            assert self.config_entry is not None
            self._last_recovery = monotonic()
            self._recovery_task = self.config_entry.async_create_background_task(
                self.hass,
                self._async_recover_connection(),
                "Marstek connection recovery",
            )

    async def _async_recover_connection(self) -> None:
        """Break a silent transport independently of a stalled polling task."""
        self.recovery_attempts += 1
        _LOGGER.warning(
            "%s: no Modbus response for 90 seconds; resetting connection", self.name
        )
        try:
            async with asyncio.timeout(RECOVERY_TIMEOUT):
                await self.timed.disconnect()
        except (ModbusError, TimeoutError) as err:
            _LOGGER.warning(
                "%s: connection reset failed (%s); will retry",
                self.name,
                type(err).__name__,
            )
        # Schedule, rather than await, polling so a stalled poll cannot prevent
        # another reset after the next recovery interval.
        assert self.config_entry is not None
        if self._recovery_refresh is None or self._recovery_refresh.done():
            self._recovery_refresh = self.config_entry.async_create_background_task(
                self.hass, self.async_request_refresh(), "Marstek recovery refresh"
            )

    def fresh(self, names: tuple[str, ...]) -> bool:
        """Whether every dependency has a successful unexpired observation."""
        return all(
            name in self.last_success
            and (
                name == "identity"
                or monotonic() - self.last_success[name] < self.stale_timeout
            )
            for name in names
        )

    def accept(self, report: UpdateReport) -> None:
        """Record only actual successes; warnings occur once per failure episode."""
        for name in report.updated:
            self.last_success[name] = monotonic()
            if self.failures.pop(name, None) is not None:
                _LOGGER.info("%s: %s recovered", self.name, name)
        for name, error in report.failed.items():
            if name not in self.failures:
                _LOGGER.warning(
                    "%s: %s read failed; retaining last observation (%s)",
                    self.name,
                    name,
                    type(error).__name__,
                )
            self.failures[name] = type(error).__name__

    async def _async_update_data(self) -> UpdateReport:
        report = await self.device.async_update_readings()
        # Never walk the slow group after a dead fast poll.
        if (
            report.updated
            and not any(
                isinstance(e, ModbusConnectionError) for e in report.failed.values()
            )
            and monotonic() >= self._slow_due
        ):
            slow = await self.device.async_update_settings()
            report.updated.update(slow.updated)
            report.failed.update(slow.failed)
            self._slow_due = monotonic() + SLOW_INTERVAL
        self.accept(report)
        try:
            await self.controls.observe(report.updated)
        except OSError as err:
            raise UpdateFailed("Cannot persist initial control snapshot") from err
        if not report.updated and not self._ever_answered:
            raise UpdateFailed("No component answered")
        self._ever_answered |= bool(report.updated)
        return report

    async def write(self, component: str, field: str, value: Any) -> None:
        """Route managed goals separately from confirmed battery-managed writes."""
        key = next(
            (
                key
                for key, spec in self.controls.specs.items()
                if spec.component == component and spec.field == field
            ),
            None,
        )
        if self.controls.managed and key is not None:
            await self.controls.set_goal(key, value)
        else:
            await self.device.async_write(component, field, value)

    @callback
    def component_updated(self, name: str) -> None:
        """Include successful write readbacks in freshness accounting."""
        self.last_success[name] = monotonic()
        self.failures.pop(name, None)
        self.async_update_listeners()


@dataclass
class MarstekRuntimeData:
    """Shared device runtime."""

    coordinator: MarstekCoordinator


type MarstekConfigEntry = ConfigEntry[MarstekRuntimeData]
