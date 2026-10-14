"""Typed component models; see the root register uncertainty note."""

from modbus_connection.model import boolean, enum, gauge, int32, integer, string, uint32

from .enums import BackupMode, ForcedMode, RS485Mode, WorkMode
from .model import MarstekComponent


class Cutoffs(MarstekComponent):
    """Optional limits; modern firmware may reject this legacy register block."""

    register_ranges = ((44000, 44001),)
    charging_cutoff_capacity = gauge(44000, 0.1, signed=False, unit="%", writable=True)
    discharging_cutoff_capacity = gauge(
        44001, 0.1, signed=False, unit="%", writable=True
    )


class AIdentity(MarstekComponent):
    """a identity register block(s)."""

    register_ranges = ((30304, 30309), (31000, 31009))
    device_name = string(31000, 10)
    ble_mac_address = string(30304, 6)


class AFirmware(MarstekComponent):
    """a firmware register block(s)."""

    register_ranges = ((30200, 30200), (30202, 30202), (30204, 30204), (30350, 30355))
    bms_version = integer(30204, signed=False)
    vms_version = integer(30202, signed=False)
    ems_version = integer(30200, signed=False)
    comm_module_firmware = string(30350, 6)


class ABattery(MarstekComponent):
    """a battery register block(s)."""

    register_ranges = ((30001, 30001), (30100, 30101), (32104, 32105))
    battery_state_of_charge = integer(32104, signed=False, unit="%")
    battery_total_energy = gauge(32105, 0.001, signed=False, unit="kWh")
    battery_voltage = gauge(30100, 0.01, signed=False, unit="V")
    battery_current = gauge(30101, 0.1, signed=True, unit="A")
    battery_power = integer(30001, signed=True, unit="W")


class ATemperatures(MarstekComponent):
    """a temperatures register block(s)."""

    register_ranges = ((35000, 35002), (35010, 35011))
    internal_temperature = gauge(35000, 0.1, signed=True, unit="°C")
    internal_mos1_temperature = gauge(35001, 0.1, signed=True, unit="°C")
    internal_mos2_temperature = gauge(35002, 0.1, signed=True, unit="°C")
    max_cell_temperature = gauge(35010, 0.1, signed=True, unit="°C")
    min_cell_temperature = gauge(35011, 0.1, signed=True, unit="°C")


class AAc(MarstekComponent):
    """a ac register block(s)."""

    register_ranges = ((30006, 30006), (32200, 32200), (32204, 32204), (37004, 37004))
    ac_voltage = gauge(32200, 0.1, signed=False, unit="V")
    ac_current = gauge(37004, 0.004, signed=True, unit="A")
    ac_power = integer(30006, signed=True, unit="W")
    ac_frequency = gauge(32204, 0.1, signed=True, unit="Hz")


class AEnergy(MarstekComponent):
    """a energy register block(s)."""

    register_ranges = ((33000, 33011),)
    total_charging_energy = uint32(33000, scale=0.01, unit="kWh")
    total_discharging_energy = int32(33002, scale=0.01, unit="kWh")
    total_daily_charging_energy = uint32(33004, scale=0.01, unit="kWh")
    total_daily_discharging_energy = int32(33006, scale=0.01, unit="kWh")
    total_monthly_charging_energy = uint32(33008, scale=0.01, unit="kWh")
    total_monthly_discharging_energy = int32(33010, scale=0.01, unit="kWh")


class AState(MarstekComponent):
    """a state register block(s)."""

    register_ranges = ((35100, 35100),)
    inverter_state_number = integer(35100, signed=False)


class ANetwork(MarstekComponent):
    """a network register block(s)."""

    register_ranges = ((30300, 30303), (41100, 41100))
    modbus_address = integer(41100, signed=False)
    wifi_signal_strength = gauge(30303, -1, signed=False, unit="dBm")
    bluetooth_status = integer(30301, signed=False)
    wifi_status = boolean(30300)
    cloud_status = boolean(30302)


class ABackupReadings(MarstekComponent):
    """a backup readings register block(s)."""

    register_ranges = ((30007, 30007), (32300, 32300))
    ac_offgrid_voltage = gauge(32300, 0.1, signed=False, unit="V")
    ac_offgrid_power = integer(30007, signed=False, unit="W")


class APv(MarstekComponent):
    """a pv register block(s)."""

    register_ranges = ((30020, 30027), (30037, 30040))
    mppt1_voltage = gauge(30020, 0.1, signed=False, unit="V")
    mppt1_current = gauge(30024, 0.1, signed=False, unit="A")
    mppt1_power = gauge(30037, 0.1, signed=False, unit="W")
    mppt2_voltage = gauge(30021, 0.1, signed=False, unit="V")
    mppt2_current = gauge(30025, 0.1, signed=False, unit="A")
    mppt2_power = gauge(30038, 0.1, signed=False, unit="W")
    mppt3_voltage = gauge(30022, 0.1, signed=False, unit="V")
    mppt3_current = gauge(30026, 0.1, signed=False, unit="A")
    mppt3_power = gauge(30039, 0.1, signed=False, unit="W")
    mppt4_voltage = gauge(30023, 0.1, signed=False, unit="V")
    mppt4_current = gauge(30027, 0.1, signed=False, unit="A")
    mppt4_power = gauge(30040, 0.1, signed=False, unit="W")


class AUserWorkMode(MarstekComponent):
    """a user work mode register block(s)."""

    register_ranges = ((43000, 43000),)
    user_work_mode = enum(43000, WorkMode, writable=True)


class AForced(MarstekComponent):
    """a forced register block(s)."""

    register_ranges = ((42010, 42010), (42020, 42021))
    forcible_charge_discharge = enum(42010, ForcedMode, writable=True)
    forcible_charge_power = integer(42020, signed=False, unit="W", writable=True)
    forcible_discharge_power = integer(42021, signed=False, unit="W", writable=True)
    # Disabled: writing 42011 activates a competing SoC-target control mode.
    # charge_to_soc = integer(42011, signed=False, unit="%", writable=True)


class ABackupFunction(MarstekComponent):
    """a backup function register block(s)."""

    register_ranges = ((41200, 41200),)
    backup_function = enum(41200, BackupMode, writable=True)


class ARs485ControlMode(MarstekComponent):
    """a rs485 control mode register block(s)."""

    register_ranges = ((42000, 42000),)
    rs485_control_mode = enum(42000, RS485Mode, writable=True)


class ALimits(MarstekComponent):
    """a limits register block(s)."""

    register_ranges = ((44002, 44003),)
    max_charge_power = integer(44002, signed=False, unit="W", writable=True)
    max_discharge_power = integer(44003, signed=False, unit="W", writable=True)


A_COMPONENTS = {
    "identity": AIdentity,
    "firmware": AFirmware,
    "battery": ABattery,
    "temperatures": ATemperatures,
    "ac": AAc,
    "energy": AEnergy,
    "state": AState,
    "network": ANetwork,
    "backup_readings": ABackupReadings,
    "pv": APv,
    "user_work_mode": AUserWorkMode,
    "forced": AForced,
    "backup_function": ABackupFunction,
    "rs485_control_mode": ARs485ControlMode,
    "limits": ALimits,
}


class DIdentity(MarstekComponent):
    """d identity register block(s)."""

    register_ranges = ((30304, 30309), (31000, 31009))
    device_name = string(31000, 10)
    ble_mac_address = string(30304, 6)


class DFirmware(MarstekComponent):
    """d firmware register block(s)."""

    register_ranges = ((30200, 30200), (30202, 30202), (30204, 30204), (30350, 30355))
    bms_version = integer(30204, signed=False)
    vms_version = integer(30202, signed=False)
    ems_version = integer(30200, signed=False)
    comm_module_firmware = string(30350, 6)


class DBattery(MarstekComponent):
    """d battery register block(s)."""

    register_ranges = ((30001, 30001), (30100, 30101), (32104, 32105))
    battery_state_of_charge = integer(32104, signed=False, unit="%")
    battery_total_energy = gauge(32105, 0.001, signed=False, unit="kWh")
    battery_voltage = gauge(30100, 0.01, signed=False, unit="V")
    battery_current = gauge(30101, 0.1, signed=True, unit="A")
    battery_power = integer(30001, signed=True, unit="W")


class DTemperatures(MarstekComponent):
    """d temperatures register block(s)."""

    register_ranges = ((35000, 35002), (35010, 35011))
    internal_temperature = gauge(35000, 0.1, signed=True, unit="°C")
    internal_mos1_temperature = gauge(35001, 0.1, signed=True, unit="°C")
    internal_mos2_temperature = gauge(35002, 0.1, signed=True, unit="°C")
    max_cell_temperature = gauge(35010, 0.1, signed=True, unit="°C")
    min_cell_temperature = gauge(35011, 0.1, signed=True, unit="°C")


class DAc(MarstekComponent):
    """d ac register block(s)."""

    register_ranges = ((30006, 30006), (32200, 32200), (32204, 32204), (37004, 37004))
    ac_voltage = gauge(32200, 0.1, signed=False, unit="V")
    ac_current = gauge(37004, 0.004, signed=True, unit="A")
    ac_power = integer(30006, signed=True, unit="W")
    ac_frequency = gauge(32204, 0.1, signed=True, unit="Hz")


class DEnergy(MarstekComponent):
    """d energy register block(s)."""

    register_ranges = ((33000, 33011),)
    total_charging_energy = uint32(33000, scale=0.01, unit="kWh")
    total_discharging_energy = int32(33002, scale=0.01, unit="kWh")
    total_daily_charging_energy = uint32(33004, scale=0.01, unit="kWh")
    total_daily_discharging_energy = int32(33006, scale=0.01, unit="kWh")
    total_monthly_charging_energy = uint32(33008, scale=0.01, unit="kWh")
    total_monthly_discharging_energy = int32(33010, scale=0.01, unit="kWh")


class DState(MarstekComponent):
    """d state register block(s)."""

    register_ranges = ((35100, 35100),)
    inverter_state_number = integer(35100, signed=False)


class DNetwork(MarstekComponent):
    """d network register block(s)."""

    register_ranges = ((30300, 30303), (41100, 41100))
    modbus_address = integer(41100, signed=False)
    wifi_signal_strength = gauge(30303, -1, signed=False, unit="dBm")
    bluetooth_status = integer(30301, signed=False)
    wifi_status = boolean(30300)
    cloud_status = boolean(30302)


class DBackupReadings(MarstekComponent):
    """d backup readings register block(s)."""

    register_ranges = ((30007, 30007), (32300, 32300))
    ac_offgrid_voltage = gauge(32300, 0.1, signed=False, unit="V")
    ac_offgrid_power = integer(30007, signed=False, unit="W")


class DPv(MarstekComponent):
    """d pv register block(s)."""

    register_ranges = ((30020, 30027), (30037, 30040))
    mppt1_voltage = gauge(30020, 0.1, signed=False, unit="V")
    mppt1_current = gauge(30024, 0.1, signed=False, unit="A")
    mppt1_power = gauge(30037, 0.1, signed=False, unit="W")
    mppt2_voltage = gauge(30021, 0.1, signed=False, unit="V")
    mppt2_current = gauge(30025, 0.1, signed=False, unit="A")
    mppt2_power = gauge(30038, 0.1, signed=False, unit="W")
    mppt3_voltage = gauge(30022, 0.1, signed=False, unit="V")
    mppt3_current = gauge(30026, 0.1, signed=False, unit="A")
    mppt3_power = gauge(30039, 0.1, signed=False, unit="W")
    mppt4_voltage = gauge(30023, 0.1, signed=False, unit="V")
    mppt4_current = gauge(30027, 0.1, signed=False, unit="A")
    mppt4_power = gauge(30040, 0.1, signed=False, unit="W")


class DUserWorkMode(MarstekComponent):
    """d user work mode register block(s)."""

    register_ranges = ((43000, 43000),)
    user_work_mode = enum(43000, WorkMode, writable=True)


class DForced(MarstekComponent):
    """d forced register block(s)."""

    register_ranges = ((42010, 42010), (42020, 42021))
    forcible_charge_discharge = enum(42010, ForcedMode, writable=True)
    forcible_charge_power = integer(42020, signed=False, unit="W", writable=True)
    forcible_discharge_power = integer(42021, signed=False, unit="W", writable=True)
    # Disabled: writing 42011 activates a competing SoC-target control mode.
    # charge_to_soc = integer(42011, signed=False, unit="%", writable=True)


class DBackupFunction(MarstekComponent):
    """d backup function register block(s)."""

    register_ranges = ((41200, 41200),)
    backup_function = enum(41200, BackupMode, writable=True)


class DRs485ControlMode(MarstekComponent):
    """d rs485 control mode register block(s)."""

    register_ranges = ((42000, 42000),)
    rs485_control_mode = enum(42000, RS485Mode, writable=True)


class DLimits(MarstekComponent):
    """d limits register block(s)."""

    register_ranges = ((44002, 44003),)
    max_charge_power = integer(44002, signed=False, unit="W", writable=True)
    max_discharge_power = integer(44003, signed=False, unit="W", writable=True)


D_COMPONENTS = {
    "identity": DIdentity,
    "firmware": DFirmware,
    "battery": DBattery,
    "temperatures": DTemperatures,
    "ac": DAc,
    "energy": DEnergy,
    "state": DState,
    "network": DNetwork,
    "backup_readings": DBackupReadings,
    "pv": DPv,
    "user_work_mode": DUserWorkMode,
    "forced": DForced,
    "backup_function": DBackupFunction,
    "rs485_control_mode": DRs485ControlMode,
    "limits": DLimits,
}


class EV3Identity(MarstekComponent):
    """e_v3 identity register block(s)."""

    register_ranges = ((30304, 30309), (31000, 31009))
    device_name = string(31000, 10)
    ble_mac_address = string(30304, 6)


class EV3Firmware(MarstekComponent):
    """e_v3 firmware register block(s)."""

    register_ranges = ((30200, 30200), (30202, 30202), (30204, 30204), (30350, 30355))
    bms_version = integer(30204, signed=False)
    vms_version = integer(30202, signed=False)
    ems_version = integer(30200, signed=False)
    comm_module_firmware = string(30350, 6)


class EV3Battery(MarstekComponent):
    """e_v3 battery register block(s)."""

    register_ranges = ((30001, 30001), (30100, 30101), (32105, 32105), (34002, 34002))
    battery_state_of_charge = gauge(34002, 0.1, signed=False, unit="%")
    battery_total_energy = gauge(32105, 0.001, signed=False, unit="kWh")
    battery_voltage = gauge(30100, 0.01, signed=False, unit="V")
    battery_current = gauge(30101, 0.1, signed=True, unit="A")
    battery_power = integer(30001, signed=True, unit="W")


class EV3Temperatures(MarstekComponent):
    """e_v3 temperatures register block(s)."""

    register_ranges = ((35000, 35002), (35010, 35011))
    internal_temperature = gauge(35000, 0.1, signed=True, unit="°C")
    internal_mos1_temperature = gauge(35001, 0.1, signed=True, unit="°C")
    internal_mos2_temperature = gauge(35002, 0.1, signed=True, unit="°C")
    max_cell_temperature = gauge(35010, 0.1, signed=True, unit="°C")
    min_cell_temperature = gauge(35011, 0.1, signed=True, unit="°C")


class EV3Ac(MarstekComponent):
    """e_v3 ac register block(s)."""

    register_ranges = ((30006, 30006), (32200, 32200), (32204, 32204), (37004, 37004))
    ac_voltage = gauge(32200, 0.1, signed=False, unit="V")
    ac_current = gauge(37004, 0.004, signed=True, unit="A")
    ac_power = integer(30006, signed=True, unit="W")
    ac_frequency = gauge(32204, 0.1, signed=True, unit="Hz")


class EV3Energy(MarstekComponent):
    """e_v3 energy register block(s)."""

    register_ranges = ((33000, 33011),)
    total_charging_energy = uint32(33000, scale=0.01, unit="kWh")
    total_discharging_energy = int32(33002, scale=0.01, unit="kWh")
    total_daily_charging_energy = uint32(33004, scale=0.01, unit="kWh")
    total_daily_discharging_energy = int32(33006, scale=0.01, unit="kWh")
    total_monthly_charging_energy = uint32(33008, scale=0.01, unit="kWh")
    total_monthly_discharging_energy = int32(33010, scale=0.01, unit="kWh")


class EV3State(MarstekComponent):
    """e_v3 state register block(s)."""

    register_ranges = ((35100, 35100),)
    inverter_state_number = integer(35100, signed=False)


class EV3Network(MarstekComponent):
    """e_v3 network register block(s)."""

    register_ranges = ((30300, 30303), (41100, 41100))
    modbus_address = integer(41100, signed=False)
    wifi_signal_strength = gauge(30303, -1, signed=False, unit="dBm")
    bluetooth_status = integer(30301, signed=False)
    wifi_status = boolean(30300)
    cloud_status = boolean(30302)


class EV3BackupReadings(MarstekComponent):
    """e_v3 backup readings register block(s)."""

    register_ranges = ((32300, 32300), (32302, 32302))
    ac_offgrid_voltage = gauge(32300, 0.1, signed=False, unit="V")
    ac_offgrid_power = integer(32302, signed=True, unit="W")


class EV3UserWorkMode(MarstekComponent):
    """e_v3 user work mode register block(s)."""

    register_ranges = ((43000, 43000),)
    user_work_mode = enum(43000, WorkMode, writable=True)


class EV3Forced(MarstekComponent):
    """e_v3 forced register block(s)."""

    register_ranges = ((42010, 42010), (42020, 42021))
    forcible_charge_discharge = enum(42010, ForcedMode, writable=True)
    forcible_charge_power = integer(42020, signed=False, unit="W", writable=True)
    forcible_discharge_power = integer(42021, signed=False, unit="W", writable=True)
    # Disabled: writing 42011 activates a competing SoC-target control mode.
    # charge_to_soc = integer(42011, signed=False, unit="%", writable=True)


class EV3BackupFunction(MarstekComponent):
    """e_v3 backup function register block(s)."""

    register_ranges = ((41200, 41200),)
    backup_function = enum(41200, BackupMode, writable=True)


class EV3Rs485ControlMode(MarstekComponent):
    """e_v3 rs485 control mode register block(s)."""

    register_ranges = ((42000, 42000),)
    rs485_control_mode = enum(42000, RS485Mode, writable=True)


class EV3Limits(MarstekComponent):
    """e_v3 limits register block(s)."""

    register_ranges = ((44002, 44003),)
    max_charge_power = integer(44002, signed=False, unit="W", writable=True)
    max_discharge_power = integer(44003, signed=False, unit="W", writable=True)


E_V3_COMPONENTS = {
    "identity": EV3Identity,
    "firmware": EV3Firmware,
    "battery": EV3Battery,
    "temperatures": EV3Temperatures,
    "ac": EV3Ac,
    "energy": EV3Energy,
    "state": EV3State,
    "network": EV3Network,
    "backup_readings": EV3BackupReadings,
    "user_work_mode": EV3UserWorkMode,
    "forced": EV3Forced,
    "backup_function": EV3BackupFunction,
    "rs485_control_mode": EV3Rs485ControlMode,
    "limits": EV3Limits,
}


class EV2Identity(MarstekComponent):
    """Venus E 2.0 identity, distinct from the modern MAC block."""

    register_ranges = ((30402, 30407), (31000, 31009))
    device_name = string(31000, 10)
    ble_mac_address = string(30402, 6)


class EV2Firmware(MarstekComponent):
    """Legacy software, EMS and BMS versions; no VMS register."""

    register_ranges = ((30800, 30805), (31100, 31102))
    software_version = gauge(31100, 0.01, signed=False)
    ems_version = integer(31101, signed=False)
    bms_version = integer(31102, signed=False)
    comm_module_firmware = string(30800, 6)


class EV2Battery(MarstekComponent):
    """Legacy battery block with signed two-word power."""

    register_ranges = ((32100, 32105),)
    battery_voltage = gauge(32100, 0.01, signed=False, unit="V")
    battery_current = gauge(32101, 0.01, signed=True, unit="A")
    battery_power = int32(32102, unit="W")
    battery_state_of_charge = integer(32104, signed=False, unit="%")
    battery_total_energy = gauge(32105, 0.001, signed=False, unit="kWh")


class EV2Ac(MarstekComponent):
    """Legacy AC block with hundredth-amp and hundredth-hertz scaling."""

    register_ranges = ((32200, 32204),)
    ac_voltage = gauge(32200, 0.1, signed=False, unit="V")
    ac_current = gauge(32201, 0.01, signed=True, unit="A")
    ac_power = int32(32202, unit="W")
    ac_frequency = gauge(32204, 0.01, signed=True, unit="Hz")


class EV2Temperatures(MarstekComponent):
    """Legacy cell extrema are whole degrees in the pinned source map."""

    register_ranges = ((35000, 35002), (35010, 35011))
    internal_temperature = gauge(35000, 0.1, signed=True, unit="°C")
    internal_mos1_temperature = gauge(35001, 0.1, signed=True, unit="°C")
    internal_mos2_temperature = gauge(35002, 0.1, signed=True, unit="°C")
    max_cell_temperature = integer(35010, signed=True, unit="°C")
    min_cell_temperature = integer(35011, signed=True, unit="°C")


class EV2BackupReadings(MarstekComponent):
    """Legacy backup measurements, including measured output current."""

    register_ranges = ((32300, 32303),)
    ac_offgrid_voltage = gauge(32300, 0.1, signed=False, unit="V")
    ac_offgrid_current = gauge(32301, 0.01, signed=False, unit="A")
    ac_offgrid_power = int32(32302, unit="W")


class EV2CellExtrema(MarstekComponent):
    """Legacy signed cell voltage extrema."""

    register_ranges = ((37007, 37008),)
    max_cell_voltage = gauge(37007, 0.001, signed=True, unit="V")
    min_cell_voltage = gauge(37008, 0.001, signed=True, unit="V")


# Only shared blocks corroborated by the legacy E 2.0 protocol map are reused.
E_V2_COMPONENTS = {
    "identity": EV2Identity,
    "firmware": EV2Firmware,
    "battery": EV2Battery,
    "temperatures": EV2Temperatures,
    "ac": EV2Ac,
    "energy": EV3Energy,
    "state": EV3State,
    "network": EV3Network,
    "backup_readings": EV2BackupReadings,
    "user_work_mode": EV3UserWorkMode,
    "forced": EV3Forced,
    "backup_function": EV3BackupFunction,
    "rs485_control_mode": EV3Rs485ControlMode,
    "cutoffs": Cutoffs,
    "limits": EV3Limits,
}
