#!/usr/bin/env python3
"""Replay the PREVIEW path captured from the app sending "hello" in red.
Preview sequence: handshake -> cmd 0x12 -> text_init -> bitmap
No display_ctrl needed — device shows content immediately in preview mode.
"""

import asyncio
from bleak import BleakClient

DEVICE_ADDRESS = "01DC102F-B8D9-1ACB-2353-441F394DA3A3"
WRITE_HANDLE = 129
NOTIFY_HANDLE = 131

last_notify = None
notify_event = asyncio.Event()

def notification_handler(sender, data):
    global last_notify
    last_notify = data
    print(f"  <- Notify: {data.hex()}")
    notify_event.set()

async def wait_for_notify(timeout=3.0):
    global last_notify
    notify_event.clear()
    last_notify = None
    try:
        await asyncio.wait_for(notify_event.wait(), timeout=timeout)
    except asyncio.TimeoutError:
        print("  <- (timeout)")
    return last_notify

async def send(client, label, hex_data):
    pkt = bytes.fromhex(hex_data)
    print(f"\n--- {label} ({len(pkt)} bytes) ---")
    print(f"  -> {hex_data}")
    await client.write_gatt_char(WRITE_HANDLE, pkt, response=False)
    resp = await wait_for_notify(3.0)
    return resp

async def main():
    print("Connecting to XyaoLED_44BF...")
    async with BleakClient(DEVICE_ADDRESS) as client:
        print(f"Connected: {client.is_connected}, MTU: {client.mtu_size}")
        await client.start_notify(NOTIFY_HANDLE, notification_handler)
        await asyncio.sleep(0.5)

        # === FIRST: hello red ===
        await send(client, "Handshake #1",
            "99aa002eff881f00000001001a02140f1b02050100435897dc6dd500000000")

        await send(client, "Text init (hello red)",
            "99aa002eff880d00040303ff00")

        await send(client, "Bitmap (hello red)",
            "99aa002eff88a4000703038c000002000201000002000300000000ff00000000ff003c001800c0061800c0061800c006d881c30678c3c6061866cc061826c80618e6cf061826c0061866c0061846c8061886cf060000000000000000000000000000000000000000000000000000000000c00100006007000030040000100c0000100c0000100c0000300c000020060000c0030000000000000000000000000000000000")
        await wait_for_notify(3.0)

        print("\n=== Check device for 'hello' red ===")
        await asyncio.sleep(5)

        # === SECOND: BBBB blue ===
        await send(client, "Handshake #2",
            "99aa002eff881f00000001001a02140f211d0501008039492eb0cb00000000")

        await send(client, "Text init (BBBB blue)",
            "99aa002eff880d00040302ff00")

        await send(client, "Bitmap (BBBB blue)",
            "99aa002eff88a4000703028c0000020002010000020003000000000000ff0000ff003c0000000000fcf0c30f841146180411441084114618fcf0c30ffcf0c30f0411441004134c300411441084114618fcf0c30f000000000000000000000000000000000000000000f0030000100600001004000010060000f0030000f003000010040000100c00001004000010060000f0030000000000000000000000000000000000")
        await wait_for_notify(3.0)

        print("\n=== Check device for BBBB blue ===")
        print("Waiting 15s before disconnect...")
        await asyncio.sleep(15)
        await client.stop_notify(NOTIFY_HANDLE)

    print("Disconnected.")

if __name__ == "__main__":
    asyncio.run(main())
