#!/usr/bin/env python3
"""Scan and list all nearby Bluetooth (BLE) devices."""

import asyncio
import sys

try:
    from bleak import BleakScanner
except ImportError:
    print("ERROR: 'bleak' is not installed. Install it with:\n  pip install bleak")
    sys.exit(1)


SCAN_DURATION = 10  # seconds


async def scan():
    print(f"Scanning for Bluetooth (BLE) devices for {SCAN_DURATION}s ...")
    devices = await BleakScanner.discover(timeout=SCAN_DURATION, return_adv=True)

    if not devices:
        print("No Bluetooth devices found.")
        return

    # devices is a dict: {address: (BLEDevice, AdvertisementData)}
    entries = []
    for addr, (dev, adv) in devices.items():
        name = dev.name or adv.local_name or "(unknown)"
        rssi = adv.rssi
        entries.append((name, addr, rssi))

    entries.sort(key=lambda x: x[2] if x[2] is not None else -999, reverse=True)

    print(f"\nFound {len(entries)} device(s):\n")
    print(f"{'#':<4} {'Name':<30} {'Address':<40} {'RSSI':>6}")
    print("-" * 82)

    for i, (name, addr, rssi) in enumerate(entries, 1):
        rssi_str = str(rssi) if rssi is not None else "N/A"
        print(f"{i:<4} {name:<30} {addr:<40} {rssi_str:>6}")

    print(f"\nDone. {len(entries)} device(s) found.")


if __name__ == "__main__":
    asyncio.run(scan())
