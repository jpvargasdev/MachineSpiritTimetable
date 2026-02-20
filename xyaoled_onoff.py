#!/usr/bin/env python3
"""XyaoLED controller - ON/OFF via BLE.
Usage: python xyaoled_onoff.py [on|off|toggle] [--stay SECONDS]
"""

import asyncio
import sys
from bleak import BleakClient

DEVICE_ADDRESS = "01DC102F-B8D9-1ACB-2353-441F394DA3A3"
WRITE_HANDLE = 129
NOTIFY_HANDLE = 131

HEADER = bytes.fromhex("99aa002eff88")
seq_counter = 0x01

def make_on_cmd(seq):
    return HEADER + bytes([0x12, 0x00, 0x11, 0x00, seq, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00])

def make_off_cmd(seq):
    return HEADER + bytes([0x12, 0x00, 0x11, 0x00, seq, 0x02, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00])

def notification_handler(sender, data):
    print(f"  <- Notification: {data.hex()}")
    if len(data) >= 12:
        state = data[11]
        print(f"     Device state: {'ON' if state == 0x01 else 'OFF'}")

async def main():
    global seq_counter

    action = sys.argv[1] if len(sys.argv) > 1 else "on"
    stay = 10  # default stay connected 10 seconds
    if "--stay" in sys.argv:
        idx = sys.argv.index("--stay")
        stay = int(sys.argv[idx + 1])

    print(f"Connecting to XyaoLED_44BF...")
    async with BleakClient(DEVICE_ADDRESS) as client:
        print(f"Connected: {client.is_connected}")
        await client.start_notify(NOTIFY_HANDLE, notification_handler)

        if action in ("on", "toggle"):
            cmd = make_on_cmd(seq_counter)
            print(f"  -> ON:  {cmd.hex()}")
            await client.write_gatt_char(WRITE_HANDLE, cmd, response=False)
            seq_counter = (seq_counter + 1) & 0xFF

        if action == "toggle":
            await asyncio.sleep(3)

        if action in ("off", "toggle"):
            cmd = make_off_cmd(seq_counter)
            print(f"  -> OFF: {cmd.hex()}")
            await client.write_gatt_char(WRITE_HANDLE, cmd, response=False)
            seq_counter = (seq_counter + 1) & 0xFF

        print(f"Staying connected for {stay}s...")
        await asyncio.sleep(stay)
        await client.stop_notify(NOTIFY_HANDLE)

    print("Disconnected.")

if __name__ == "__main__":
    asyncio.run(main())
