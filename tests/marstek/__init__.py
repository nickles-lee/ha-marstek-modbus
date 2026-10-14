"""Marstek integration tests."""

from modbus_connection.mock import MockModbusConnection

from custom_components.marstek._vendor.marstek_modbus import MarstekBattery, Model

DATA = {
    "host": "192.0.2.1",
    "port": 502,
    "unit_id": 1,
    "model": "e_v3",
    "pack_count": 1,
    "battery_slot": 1,
    "control_management": "battery_managed",
}
MAC = "aa:bb:cc:dd:ee:ff"


def seed(connection: MockModbusConnection, model: Model = Model.E_V3):
    """A register-complete simulated battery."""
    unit = connection.for_unit(1)
    device = MarstekBattery(unit, model)
    for component in device.components.values():
        for resolved in component.resolved_fields.values():
            for offset in range(resolved.count):
                unit.holding[resolved.address + offset] = 0
    for address, text in [
        (30402 if model is Model.E_V2 else 30304, "AABBCCDDEEFF"),
        (31000, "VENUS"),
    ]:
        encoded = text.encode()
        for i in range(0, len(encoded), 2):
            unit.holding[address + i // 2] = int.from_bytes(encoded[i : i + 2], "big")
    unit.holding.update(
        {
            30100: 5120,
            30101: 100,
            30001: 512,
            30006: 500,
            32104: 50,
            34002: 500,
            32105: 5120,
            35100: 2,
            42000: 21930,
            42011: 100,
            32300: 2300,
            32302: 100,
            44000: 1000,
            44001: 120,
            44002: 1500,
            44003: 1500,
        }
    )
    if model is Model.E_V2:
        unit.holding.update(
            {
                32100: 5120,
                32101: 1000,
                32102: 0,
                32103: 512,
                32202: 0,
                32203: 500,
                32302: 0,
                32303: 100,
            }
        )
    return unit
