"""Protocol fixtures with realistic identity and explicit register storage."""

import pytest
from modbus_connection.mock import MockModbusConnection, MockModbusUnit

from marstek_modbus import MarstekBattery, Model


@pytest.fixture
def unit() -> MockModbusUnit:
    return MockModbusConnection().for_unit(1)


def seed(
    unit: MockModbusUnit, model: Model = Model.E_V3, packs: int = 1
) -> MarstekBattery:
    device = MarstekBattery(unit, model, pack_count=packs)
    for component in device.components.values():
        for resolved in component.resolved_fields.values():
            for offset in range(resolved.count):
                unit.holding[resolved.address + offset] = 0

    def string(address: int, text: str) -> None:
        encoded = text.encode()
        for i in range(0, len(encoded), 2):
            unit.holding[address + i // 2] = int.from_bytes(encoded[i : i + 2], "big")

    string(30402 if model is Model.E_V2 else 30304, "AABBCCDDEEFF")
    string(31000, "VNSD-0" if model is Model.D else "VENUS")
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
    return device
