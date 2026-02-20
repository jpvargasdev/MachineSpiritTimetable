#!/usr/bin/env python3
"""Replay the exact captured CCCC sequence to the XyaoLED device.
If the display changes from BBBB to CCCC, we know the protocol works."""

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
        await client.start_notify(NOTIFY_HANDLE, notification_handler)
        await asyncio.sleep(1)

        # Exact captured CCCC sequence from btsnoop_bbcc.log (packets 4100-4121)
        
        # Packet #4100: handshake (cmd 0x00)
        pkt1 = bytes.fromhex("99aa002eff881f00000001001a02140e04240501007f5b027a064d00000000")
        # Packet #4104: config (cmd 0x0f)
        pkt2 = bytes.fromhex("99aa002eff880f000a000200000000")
        # Packet #4108: text init page 1 (cmd 0x04, seq=0x03, color=ff00)
        pkt3 = bytes.fromhex("99aa002eff880d00040203ff00")
        # Packet #4114: bitmap data page 1 (cmd 0x07, seq=0x03, 164 bytes)
        pkt4 = bytes.fromhex("99aa002eff88a4000702038c000002000201000002000300000000ff00000000ff003c0000000000fcf0c30f841146180411441084114618fcf0c30ffcf0c30f0411441004134c300411441084114618fcf0c30f000000000000000000000000000000000000000000f0030000100600001004000010060000f0030000f003000010040000100c00001004000010060000f0030000000000000000000000000000000000")
        # Packet #4118: text init page 2 (cmd 0x04, seq=0x04, color=ff00)
        pkt5 = bytes.fromhex("99aa002eff880d00040204ff00")
        # Packet #4121: bitmap data page 2 (cmd 0x07, seq=0x04, 164 bytes)
        pkt6 = bytes.fromhex("99aa002eff88a4000702048c000002000201000002000300000000ff00000000ff003c00001ce000007ff80380010c00c0000600c0000600c0000600c0000600c0000600c00006008000040080431c02003ff80100000000000000000000000000000000001ce000007ff80380010c00c0000600c0000600c0000600c0000600c0000600c00006008000040080431c02003ff80100000000000000000000000000000000")

        packets = [
            ("handshake",       pkt1),
            ("config",          pkt2),
            ("text_init_p1",    pkt3),
            ("bitmap_p1",       pkt4),
            ("text_init_p2",    pkt5),
            ("bitmap_p2",       pkt6),
        ]

        for name, pkt in packets:
            print(f"  -> {name:15s} ({len(pkt):3d} bytes): {pkt.hex()}")
            await client.write_gatt_char(WRITE_HANDLE, pkt, response=False)
            await asyncio.sleep(0.3)

        print("\nWaiting 10s for notifications...")
        await asyncio.sleep(10)
        await client.stop_notify(NOTIFY_HANDLE)

    print("Disconnected.")

if __name__ == "__main__":
    asyncio.run(main())
