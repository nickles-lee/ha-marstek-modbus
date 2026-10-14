"""Protocol codes and device capabilities."""

from enum import IntEnum, IntFlag, StrEnum


class Model(StrEnum):
    """Supported register-map variants."""

    A = "a"
    D = "d"
    E_V2 = "e_v2"
    E_V3 = "e_v3"

    @property
    def max_power(self) -> int:
        """Maximum configurable AC power in watts."""
        return 1500 if self is Model.A else 2500

    @property
    def max_packs(self) -> int:
        """Maximum number of physical packs."""
        return {Model.A: 6, Model.D: 7, Model.E_V2: 1, Model.E_V3: 1}[self]

    @property
    def cells(self) -> int:
        """Cells in a pack."""
        return 13 if self is Model.A else 16


class Capability(IntFlag):
    """Subsystems physically present on a model."""

    BATTERY = 1
    BACKUP = 2
    PV = 4
    EXPANDABLE = 8


class ForcedMode(IntEnum):
    """Forced power direction."""

    STOP = 0
    CHARGE = 1
    DISCHARGE = 2


class WorkMode(IntEnum):
    """App-controlled work mode; AI readback is firmware-dependent."""

    MANUAL = 0
    ANTI_FEED = 1
    AI = 2


class RS485Mode(IntEnum):
    """External-control command and readback codes."""

    ENABLE = 0x55AA
    DISABLE = 0x55BB


class BackupMode(IntEnum):
    """Backup output enable code (inverted polarity)."""

    ENABLE = 0
    DISABLE = 1


class Weekday(IntFlag):
    """Schedule days, Monday in bit zero."""

    MONDAY = 1
    TUESDAY = 2
    WEDNESDAY = 4
    THURSDAY = 8
    FRIDAY = 16
    SATURDAY = 32
    SUNDAY = 64
