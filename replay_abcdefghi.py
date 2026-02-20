#!/usr/bin/env python3
"""Replay ABCDEFGHI with MTU negotiation."""

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
        
        # Check MTU
        mtu = client.mtu_size
        print(f"Current MTU: {mtu}")
        
        await client.start_notify(NOTIFY_HANDLE, notification_handler)
        await asyncio.sleep(1)

        # Try requesting larger MTU (app requests 503)
        # On macOS with bleak, MTU negotiation happens automatically
        # but let's see what we get

        # Exact captured ABCDEFGHI sequence
        pkt1 = bytes.fromhex("99aa002eff881f00000001001a02140e1635050100fb4ab5a6425400000000")
        pkt2 = bytes.fromhex("99aa002eff880f000a000200000000")
        pkt3 = bytes.fromhex("99aa002eff880d00040203ff00")
        pkt4 = bytes.fromhex("99aa002eff8824010702030c0100020002010000040003000000000000ff0000ff003c00000000000006fc00000e8401000b0401000984010019fc008011fc00801f0401c030040340200401406084016040fc0000000000000000000000000000000000c0010000f0e70f3f182018010c2010010c2030010c20303f0c20303f0c2030010c2010010820180138240c01f0e3073f0000000000000000000000000000000000c000007ef82310020c201002042010020620100206e01f7e82e31f020622100206221002042210021c221002f02310000000000000000000000000000000000000000000c003000080000000800000")

        print(f"\nBitmap packet size: {len(pkt4)} bytes, MTU: {mtu}")
        if len(pkt4) > mtu - 3:
            print(f"WARNING: Packet ({len(pkt4)}) exceeds MTU payload ({mtu-3})!")
            print("The packet will likely be truncated or rejected.")

        packets = [
            ("handshake",   pkt1),
            ("config",      pkt2),
            ("text_init",   pkt3),
            ("bitmap_data", pkt4),
        ]

        for name, pkt in packets:
            print(f"  -> {name:15s} ({len(pkt):3d} bytes)")
            await client.write_gatt_char(WRITE_HANDLE, pkt, response=False)
            await asyncio.sleep(0.5)

        print("\nWaiting 10s for notifications...")
        await asyncio.sleep(10)
        await client.stop_notify(NOTIFY_HANDLE)

    print("Disconnected.")

if __name__ == "__main__":
    asyncio.run(main())
