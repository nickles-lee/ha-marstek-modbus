"""Compatibility with the unit API shipped in Home Assistant 2026.9."""

from unittest.mock import Mock

import pytest

from marstek_modbus.tuning import TimedUnit


def test_legacy_unit_tuning() -> None:
    """Use defaults on old units without silently accepting unsupported tuning."""
    unit = Mock(spec=["set_message_spacing"])
    timed = TimedUnit(unit)
    timed.require_timeout(None)
    timed.require_connect_delay(None)
    timed.set_message_spacing(0.08)
    unit.set_message_spacing.assert_called_once_with(0.08)
    with pytest.raises(ValueError, match="Timeout tuning requires"):
        timed.require_timeout(5)
    with pytest.raises(ValueError, match="Connect-delay tuning requires"):
        timed.require_connect_delay(0.5)


def test_modern_unit_tuning() -> None:
    """Forward tuning and withdrawal to modern shared connection requirements."""
    unit = Mock(spec=["require_timeout", "require_connect_delay"])
    timed = TimedUnit(unit)
    timed.require_timeout(5)
    unit.require_timeout.assert_called_once_with(5)
    timed.require_timeout(None)
    unit.require_timeout.assert_called_with(None)
    timed.require_connect_delay(0.5)
    unit.require_connect_delay.assert_called_once_with(0.5)
