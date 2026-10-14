"""Repeated packs and schedule components with explicit placement."""

from modbus_connection.model import boolean, flags, gauge, integer

from .enums import Weekday
from .model import MarstekComponent


class Schedule(MarstekComponent):
    """One five-register schedule; placed with a base offset."""

    register_ranges = ((43100, 43104),)
    days = flags(43100, Weekday, writable=True)
    start = integer(43101, signed=False, writable=True)
    end = integer(43102, signed=False, writable=True)
    mode = integer(43103, signed=True, writable=True)
    enabled = boolean(43104, writable=True)


class Pack(MarstekComponent):
    """Common pack observations; each pack is refreshed independently."""

    state_of_charge = gauge(34002, 0.1, signed=False, unit="%")
    cycle_count = integer(34003, signed=False)
    cell_1_voltage = gauge(34018, 0.001, signed=False, unit="V")
    cell_2_voltage = gauge(34019, 0.001, signed=False, unit="V")
    cell_3_voltage = gauge(34020, 0.001, signed=False, unit="V")
    cell_4_voltage = gauge(34021, 0.001, signed=False, unit="V")
    cell_5_voltage = gauge(34022, 0.001, signed=False, unit="V")
    cell_6_voltage = gauge(34023, 0.001, signed=False, unit="V")
    cell_7_voltage = gauge(34024, 0.001, signed=False, unit="V")
    cell_8_voltage = gauge(34025, 0.001, signed=False, unit="V")
    cell_9_voltage = gauge(34026, 0.001, signed=False, unit="V")
    cell_10_voltage = gauge(34027, 0.001, signed=False, unit="V")
    cell_11_voltage = gauge(34028, 0.001, signed=False, unit="V")
    cell_12_voltage = gauge(34029, 0.001, signed=False, unit="V")
    cell_13_voltage = gauge(34030, 0.001, signed=False, unit="V")
    cell_14_voltage = gauge(34031, 0.001, signed=False, unit="V")
    cell_15_voltage = gauge(34032, 0.001, signed=False, unit="V")
    cell_16_voltage = gauge(34033, 0.001, signed=False, unit="V")


class DPack(Pack):
    """Additional Venus D pack scalars corroborated by device scans."""

    voltage = gauge(34000, 0.01, signed=False, unit="V")
    current = gauge(34001, 0.1, signed=True, unit="A")
    charge_status = integer(34004, signed=False)
    max_cell_voltage = gauge(34005, 0.001, signed=False, unit="V")
    min_cell_voltage = gauge(34006, 0.001, signed=False, unit="V")
    max_temperature = gauge(34007, 0.1, signed=False, unit="°C")
    protection_1 = integer(34008, signed=False)
    protection_2 = integer(34009, signed=False)
    bms_version = integer(34010, signed=False)
    temperature_0 = gauge(34011, 0.1, signed=False, unit="°C")
    temperature_1 = gauge(34012, 0.1, signed=False, unit="°C")
    temperature_2 = gauge(34013, 0.1, signed=False, unit="°C")
    temperature_3 = gauge(34014, 0.1, signed=False, unit="°C")
    temperature_4 = gauge(34015, 0.1, signed=False, unit="°C")
    temperature_5 = gauge(34016, 0.1, signed=False, unit="°C")
    temperature_6 = gauge(34017, 0.1, signed=False, unit="°C")


class CellExtrema(MarstekComponent):
    """Global cell voltage extremes shared by the modern profiles."""

    register_ranges = ((37007, 37008),)
    max_cell_voltage = gauge(37007, 0.001, signed=False, unit="V")
    min_cell_voltage = gauge(37008, 0.001, signed=False, unit="V")
