#!/usr/bin/env python3
"""Connect to XyaoLED BLE device and enumerate all services/characteristics."""

import asyncio
import sys

try:
    from bleak import BleakClient, BleakScanner
except ImportError:
    print("ERROR: 'bleak' is not installed. Install it with:\n  pip install bleak")
    sys.exit(1)


TARGET_NAME = "XyaoLED"
SCAN_DURATION = 10  # seconds


async def find_device():
    """Scan and return the first device whose name contains TARGET_NAME."""
    print(f"Scanning for '{TARGET_NAME}' ...")
    devices = await BleakScanner.discover(timeout=SCAN_DURATION, return_adv=True)
    for addr, (dev, adv) in devices.items():
        name = dev.name or adv.local_name or ""
        if TARGET_NAME.lower() in name.lower():
            print(f"Found: {name}  ({addr})  RSSI={adv.rssi}")
            return dev
    return None


def char_props(char):
    """Return a human-readable list of characteristic properties."""
    return ", ".join(sorted(char.properties))


async def main():
    dev = await find_device()
    if not dev:
        print(f"Could not find a device matching '{TARGET_NAME}'.")
        sys.exit(1)

    print(f"\nConnecting to {dev.name} ({dev.address}) ...")
    async with BleakClient(dev) as client:
        print(f"Connected: {client.is_connected}\n")

        print("=" * 80)
        print("SERVICES & CHARACTERISTICS")
        print("=" * 80)

        for service in client.services:
            print(f"\n[Service] {service.uuid}")
            print(f"  Description: {service.description or '(unknown)'}")

            for char in service.characteristics:
                props = char_props(char)
                print(f"\n  [Char] {char.uuid}")
                print(f"    Description : {char.description or '(unknown)'}")
                print(f"    Properties  : {props}")
                print(f"    Handle      : {char.handle}")

                # Try to read the value if readable
                if "read" in char.properties:
                    try:
                        value = await client.read_gatt_char(char.uuid)
                        print(f"    Value (hex) : {value.hex()}")
                        print(f"    Value (raw) : {value}")
                        try:
                            print(f"    Value (utf8): {value.decode('utf-8', errors='replace')}")
                        except Exception:
                            pass
                    except Exception as e:
                        print(f"    Value       : <read failed: {e}>")

                for desc in char.descriptors:
                    print(f"    [Desc] {desc.uuid}: {desc.description or '(unknown)'}")

        print("\n" + "=" * 80)
        print("Done. Review the output above to identify writable characteristics.")
        print("Look for characteristics with 'write' or 'write-without-response' properties.")
        print("=" * 80)


if __name__ == "__main__":
    asyncio.run(main())
