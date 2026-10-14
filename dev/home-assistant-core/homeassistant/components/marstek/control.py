"""Persistent control goals, independent of firmware observations."""

import asyncio
import logging
from time import monotonic
from typing import TYPE_CHECKING, Any

from modbus_connection import ModbusError

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.storage import Store

from .const import CONF_CONTROL_MANAGEMENT, DOMAIN, HA_MANAGED
from .descriptions import CONTROL_KEYS, OPTIONS, Description, descriptions

if TYPE_CHECKING:
    from .coordinator import MarstekCoordinator

_LOGGER = logging.getLogger(__name__)
HEARTBEAT = 60.0
SETTLE = 5.0
OPTIONAL_KEYS = frozenset({"charging_cutoff_capacity", "discharging_cutoff_capacity"})
RS485 = "rs485_control_mode"
WORK_MODE = "user_work_mode"
# Direction is always applied after its powers and limits.
ORDER = (
    RS485,
    "max_charge_power",
    "max_discharge_power",
    "backup_function",
    # "charge_to_soc",
    "charging_cutoff_capacity",
    "discharging_cutoff_capacity",
    "forcible_charge_power",
    "forcible_discharge_power",
    "forcible_charge_discharge",
    WORK_MODE,
)


class ManagedControls:
    """One durable goal set and one coalescing worker per config entry."""

    def __init__(self, coordinator: MarstekCoordinator) -> None:
        """Bind storage and model-supported controls."""
        self.coordinator = coordinator
        entry = coordinator.config_entry
        assert entry is not None
        self.mode = entry.data[CONF_CONTROL_MANAGEMENT]
        self.specs = {
            spec.key: spec
            for spec in descriptions(
                coordinator.device.model, coordinator.device.pack_count
            )
            if spec.key in CONTROL_KEYS
        }
        self.goals: dict[str, int | float] = {}
        self.dirty: set[str] = set()
        self.errors: dict[str, str] = {}
        self.attempts: dict[str, int | float] = {}
        self._store: Store[dict[str, Any]] = Store(
            coordinator.hass, 1, f"{DOMAIN}.control.{entry.entry_id}"
        )
        self._save_lock = asyncio.Lock()
        self._task: asyncio.Task[None] | None = None
        self._started = False
        self._generation = 0
        self._next_attempt = 0.0
        self._heartbeat = 0.0
        self._settle_until = 0.0
        self._failures = 0
        self._online = False

    @property
    def managed(self) -> bool:
        """Whether HA owns the control goals."""
        return self.mode == HA_MANAGED

    @property
    def ready(self) -> bool:
        """Require the primary snapshot; optional cutoffs cannot block it."""
        return self.specs.keys() - OPTIONAL_KEYS <= self.goals.keys()

    def owns(self, spec: Description) -> bool:
        """Whether an entity displays a retained goal."""
        return self.managed and spec.key in self.specs

    def observed(self, key: str) -> Any:
        """Return a cached battery observation, never a goal."""
        spec = self.specs[key]
        return getattr(self.coordinator.device.components[spec.component], spec.field)

    def active(self, key: str) -> bool:
        """Work mode and external control are mutually exclusive."""
        if RS485 not in self.goals or key not in self.goals:
            return False
        if key in OPTIONAL_KEYS and not self.coordinator.fresh(self.specs[key].sources):
            return False
        enabled = self.goals[RS485] == OPTIONS[RS485]["enable"]
        return key == RS485 or (key != WORK_MODE if enabled else key == WORK_MODE)

    def validate(self, key: str, value: Any) -> None:
        """Use the library's protocol and physical bounds without I/O."""
        spec = self.specs[key]
        self.coordinator.device.components[spec.component].validate_write(
            spec.field, value
        )

    async def _save(self, goals: dict[str, int | float]) -> None:
        await self._store.async_save(
            {
                "mode": self.mode,
                "model": self.coordinator.device.model.value,
                "goals": goals,
            }
        )

    async def async_load(self) -> None:
        """Restore goals; mode transitions start a fresh snapshot."""
        saved = await self._store.async_load()
        if (
            saved
            and saved.get("mode") == self.mode
            and self.managed
            and saved.get("model") == self.coordinator.device.model.value
        ):
            for key, value in saved.get("goals", {}).items():
                if key in self.specs:
                    self.validate(key, value)
                    self.goals[key] = value
        else:
            await self._save({})
        if saved and saved.get("goals") != self.goals:
            # Drop retired commands while preserving every supported saved goal.
            await self._save(self.goals)
        self.dirty.update(self.goals)

    async def observe(self, updated: set[str]) -> None:
        """Seed missing goals once, using only successful validated reads."""
        if not self.managed:
            return
        async with self._save_lock:
            goals = dict(self.goals)
            for key, spec in self.specs.items():
                if key in goals or spec.component not in updated:
                    continue
                value = self.observed(key)
                try:
                    self.validate(key, value)
                except ValueError, TypeError:
                    continue
                goals[key] = value
            if goals != self.goals:
                await self._save(goals)
                self.goals = goals
                self.dirty.update(goals)
        if updated and not self._online:
            self._next_attempt = 0.0
            self._settle_until = 0.0
            self._heartbeat = 0.0
            self.dirty.update(self.goals)
        self._online = bool(updated)
        self.request()

    async def set_goal(self, key: str, value: Any) -> None:
        """Commit intent before displaying it or scheduling device writes."""
        self.validate(key, value)
        async with self._save_lock:
            normalized = int(value) if int(value) == value else round(value, 1)
            goals = {**self.goals, key: normalized}
            try:
                await self._save(goals)
            except OSError as err:
                raise HomeAssistantError("Could not persist control goal") from err
            if not self._failures:
                self._next_attempt = 0.0
            changed_authority = key == RS485 and self.goals.get(key) != int(value)
            self.goals = goals
            self._generation += 1
            self.dirty.add(key)
            if changed_authority:
                self._next_attempt = 0.0
                self._failures = 0
                self.dirty.update(self.specs)
                self._settle_until = 0.0
            self.coordinator.async_update_listeners()
        self.request()

    def start(self) -> None:
        """Start after first refresh and platform setup."""
        self._started = True
        self.request()

    def stop(self) -> None:
        """Cancel pending commands when unloading the entry."""
        self._started = False
        if self._task is not None:
            self._task.cancel()

    def request(self) -> None:
        """Coalesce requests; timers resume settling and transport backoff."""
        now = monotonic()
        if (
            not self._started
            or not self.managed
            or not self.ready
            or now < max(self._next_attempt, self._settle_until)
            or (self._task is not None and not self._task.done())
        ):
            return
        entry = self.coordinator.config_entry
        assert entry is not None
        self._task = entry.async_create_background_task(
            self.coordinator.hass, self._apply(), "Marstek control reconciliation"
        )

    def status(self, key: str) -> str:
        """Separate suppression from failure to converge."""
        if key not in self.goals:
            return "initializing"
        if not self.active(key):
            return "deferred"
        spec = self.specs[key]
        if (
            key in self.dirty
            or key in self.errors
            or not self.coordinator.fresh(spec.sources)
            or self.observed(key) != self.goals[key]
        ):
            return "pending"
        return "converged"

    def in_sync(self, key: str | None = None) -> bool | None:
        """Compare fresh observations to active goals, independently of retries."""
        if (
            not self.managed
            or RS485 not in self.goals
            or (key is None and not self.ready)
        ):
            return None
        enabled = self.goals[RS485] == OPTIONS[RS485]["enable"]
        # Include retained optional goals even when their observations are stale.
        # Their freshness must affect sync status, not silently exclude them.
        keys = [
            name
            for name in self.specs
            if name in self.goals
            and (name == RS485 or (name != WORK_MODE if enabled else name == WORK_MODE))
        ]
        if key is not None:
            if key not in keys:
                return None
            keys = [key]
        if not keys or any(
            not self.coordinator.fresh(self.specs[name].sources)
            or self.observed(name) is None
            for name in keys
        ):
            return None
        return all(self.observed(name) == self.goals[name] for name in keys)

    def diagnostics(self) -> dict[str, Any]:
        """Report control ownership and convergence without device requests."""
        return {
            "mode": self.mode,
            "initialized": self.ready,
            "goals": dict(self.goals),
            "status": {key: self.status(key) for key in self.specs}
            if self.managed
            else {},
            "attempts": dict(self.attempts),
            "errors": dict(self.errors),
        }

    async def _apply(self) -> None:
        """Apply each selected field once, using current intent under device lock."""
        now = monotonic()
        heartbeat = now >= self._heartbeat
        pending = {
            key
            for key, spec in self.specs.items()
            if self.active(key)
            and (
                heartbeat
                or key in self.dirty
                or key in self.errors
                or (
                    self.coordinator.fresh(spec.sources)
                    and self.observed(key) != self.goals[key]
                )
            )
        }
        if self._settle_until:
            # An acknowledged authority write is sufficient: a lying readback
            # must not prevent the remaining controls from ever being applied.
            pending.discard(RS485)
            self._settle_until = 0.0
        generation = self._generation
        for key in ORDER:
            if key not in pending:
                continue
            if generation != self._generation or not self._started:
                return
            spec = self.specs[key]
            value = self.goals[key]
            try:
                async with asyncio.timeout(30):
                    applied = await self.coordinator.device.async_write_control(
                        spec.component,
                        spec.field,
                        value,
                        is_current=lambda key=key: (
                            self._started
                            and generation == self._generation
                            and self.active(key)
                        ),
                    )
            except (ModbusError, TimeoutError) as err:
                self.attempts[key] = self.attempts.get(key, 0) + 1
                if key not in self.errors:
                    _LOGGER.warning(
                        "%s: control %s pending (%s)",
                        self.coordinator.name,
                        key,
                        type(err).__name__,
                    )
                self.errors[key] = type(err).__name__
                if key in OPTIONAL_KEYS:
                    # A rejected optional limit cannot suppress power/direction.
                    self.coordinator.async_update_listeners()
                    continue
                self._failures += 1
                self._next_attempt = (
                    monotonic() + (10, 20, 40, 60)[min(self._failures - 1, 3)]
                )
                self.coordinator.async_update_listeners()
                return
            if not applied:
                return
            self.attempts[key] = self.attempts.get(key, 0) + 1
            if self.errors.pop(key, None) is not None:
                _LOGGER.info(
                    "%s: control %s writes recovered", self.coordinator.name, key
                )
            if generation != self._generation:
                return
            self.dirty.discard(key)
            self._next_attempt = 0.0
            if key == RS485:
                # Continue on the independent timer rather than sleeping with a
                # task (or the device lock) held during firmware settling.
                self.dirty.update(
                    key for key in self.specs if key != RS485 and self.active(key)
                )
                self._settle_until = monotonic() + SETTLE
                self._heartbeat = monotonic() + HEARTBEAT
                self.coordinator.async_update_listeners()
                return
        self._failures = 0
        if heartbeat:
            self._heartbeat = monotonic() + HEARTBEAT
        self._next_attempt = min(monotonic() + 10, self._heartbeat)
        self.coordinator.async_update_listeners()
