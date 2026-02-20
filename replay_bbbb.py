#!/usr/bin/env python3
"""Replay BBBB - the small 100-byte version that's similar to CCCC which worked."""

import asyncio
from bleak import BleakClient

DEVICE_ADDRESS = "01DC102F-B8D9-1ACB-2353-441F394DA3A3"
WRITE_HANDLE = 129
NOTIFY_HANDLE = 131

def notification_handler(sender, data):
    print(f"  <- Notify: {data.hex()}")

async def main():
    print("Connecting to XyaoLED_44BF...")
    async with BleakClient(DEVICE_ADDRESS) as client:
        print(f"Connected: {client.is_connected}")
        print(f"MTU: {client.mtu_size}")
        await client.start_notify(NOTIFY_HANDLE, notification_handler)
        await asyncio.sleep(1)

        # From btsnoop_bbcc.log - the clean BBBB capture
        # Just text_init + bitmap + activate (no display_ctrl that turns things off)
        
        # text init (cmd 0x04, seq=0x02, color=ff00 red)
        pkt1 = bytes.fromhex("99aa002eff880d00040202ff00")
        # bitmap data (cmd 0x07, seq=0x02, 100 bytes)
        pkt2 = bytes.fromhex("99aa002eff8864000702024c000002000201000001000300000000ff00000000ff003c00000000000081780000811000008110000081100000ff100000ff1000008110000081100000811000008110000081780000000000000000000000000000000000")
        # activate (cmd 0x11 with enable) - using seq matching
        pkt3 = bytes.fromhex("99aa002eff88120011000202010100000000")

        packets = [
            ("text_init",   pkt1),
            ("bitmap_data", pkt2),
            ("activate",    pkt3),
        ]

        for name, pkt in packets:
            print(f"  -> {name:15s} ({len(pkt):3d} bytes): {pkt.hex()}")
            await client.write_gatt_char(WRITE_HANDLE, pkt, response=False)
            await asyncio.sleep(0.5)

        print("\nWaiting 10s for notifications...")
        await asyncio.sleep(10)
        await client.stop_notify(NOTIFY_HANDLE)

    print("Disconnected.")

if __name__ == "__main__":
    asyncio.run(main())
