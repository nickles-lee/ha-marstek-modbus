#!/usr/bin/env python3
"""Read a battery once and report decoded values, failures and request timing."""

import argparse
import asyncio
import json
from dataclasses import asdict

from modbus_connection import ModbusError
from modbus_connection.cli_helper import (
    add_connection_args,
    connect_from_args,
    print_component,
)

from marstek_modbus import MarstekBattery, Model
from marstek_modbus.tuning import TimedUnit


def build_parser() -> argparse.ArgumentParser:
    """Create the diagnostic command-line parser."""
    parser = argparse.ArgumentParser(description=__doc__)
    add_connection_args(parser, connections=(("tcp", "socket"),))
    parser.add_argument("--model", choices=[m.value for m in Model], required=True)
    parser.add_argument("--packs", type=int, default=1)
    parser.add_argument("--unit", type=int, default=1)
    parser.add_argument("--raw", action="store_true")
    parser.add_argument("--spacing", type=float, default=0.16)
    return parser


async def main() -> int:
    """Run a read-only TCP diagnostic query."""
    args = build_parser().parse_args()
    connection = await connect_from_args(args)
    unit = TimedUnit(connection.for_unit(args.unit))
    unit.set_message_spacing(args.spacing)
    try:
        device = MarstekBattery(unit, Model(args.model), pack_count=args.packs)
        report = await device.async_update()
        for name, component in device.components.items():
            print_component(component, title=name)
        print(
            "Failures:",
            {name: type(err).__name__ for name, err in report.failed.items()},
        )
        print("Timing:", json.dumps(asdict(unit.stats)))
        if args.raw:
            print(json.dumps(await device.async_read_raw(), indent=2))
        return 0 if report.complete else 2
    except (ModbusError, ValueError) as err:
        print(f"Query failed: {err}")
        return 1
    finally:
        await connection.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
