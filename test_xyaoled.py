#!/usr/bin/env python3
"""
Test script for XyaoLED BLE LED matrix.

Based on reverse-engineered Zengge LEDnetWF protocol.
Reference: https://github.com/8none1/zengge_lednetwf

Connects to the device, subscribes to notifications, and lets you
send common commands to discover what works.
"""

import asyncio
import sys

try:
    from bleak import BleakClient, BleakScanner
except ImportError:
    print("ERROR: 'bleak' is not installed. Install it with:\n  pip install bleak")
    sys.exit(1)


TARGET_NAME = "XyaoLED"
SCAN_DURATION = 10

# Service and characteristic UUIDs from our exploration
SERVICE_UUID      = "0000ae30-0000-1000-8000-00805f9b34fb"
WRITE_CHAR_UUID   = "0000ae01-0000-1000-8000-00805f9b34fb"  # write-without-response (handle 5)
NOTIFY_CHAR_UUID  = "0000ae02-0000-1000-8000-00805f9b34fb"  # notify (handle 7)
WRITE2_CHAR_UUID  = "0000ae03-0000-1000-8000-00805f9b34fb"  # write-without-response (handle 10)
NOTIFY2_CHAR_UUID = "0000ae04-0000-1000-8000-00805f9b34fb"  # notify (handle 12)
RW_CHAR_UUID      = "0000ae10-0000-1000-8000-00805f9b34fb"  # read/write (handle 18)

# Also try the secondary service
SERVICE2_UUID     = "0000ae3a-0000-1000-8000-00805f9b34fb"
WRITE3_CHAR_UUID  = "0000ae3b-0000-1000-8000-00805f9b34fb"  # write-without-response (handle 65)
NOTIFY3_CHAR_UUID = "0000ae3c-0000-1000-8000-00805f9b34fb"  # notify (handle 67)

# Also try the third service
SERVICE3_UUID     = "0000ae00-0000-1000-8000-00805f9b34fb"
WRITE4_CHAR_UUID  = "0000ae01-0000-1000-8000-00805f9b34fb"  # handle 129
NOTIFY4_CHAR_UUID = "0000ae02-0000-1000-8000-00805f9b34fb"  # handle 131

# Global packet counter
counter = 0


def next_counter():
    global counter
    counter += 1
    if counter > 0xFFFF:
        counter = 1
    return counter


# ─── Zengge-style command builders ────────────────────────────────────────────

def zengge_power_on():
    """Zengge protocol: power ON"""
    c = next_counter()
    return bytes([
        (c >> 8) & 0xFF, c & 0xFF,  # counter
        0x80, 0x00,                  # header
        0x00, 0x0D, 0x0E,           # length
        0x0B, 0x3B, 0x23,           # command: ON
        0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x32,
        0x00, 0x00, 0x90            # checksum (ignored per docs)
    ])


def zengge_power_off():
    """Zengge protocol: power OFF"""
    c = next_counter()
    return bytes([
        (c >> 8) & 0xFF, c & 0xFF,
        0x80, 0x00,
        0x00, 0x0D, 0x0E,
        0x0B, 0x3B, 0x24,
        0x00, 0x00, 0x00, 0x00,
        0x00, 0x00, 0x00, 0x32,
        0x00, 0x00, 0x91
    ])


def zengge_set_rgb(r, g, b, brightness=100):
    """Zengge protocol: set static RGB colour (strip firmware style)"""
    c = next_counter()
    csum = (0x41 + 0x02 + r + g + b + 0 + 0 + 0 + brightness + 0 + 0 + 0xF0) & 0xFF
    return bytes([
        (c >> 8) & 0xFF, c & 0xFF,
        0x80, 0x00,
        0x00, 0x0D, 0x0E,
        0x0B, 0x41, 0x02,           # static colour mode
        r, g, b,                     # RGB
        0x00, 0x00, 0x00,           # background
        brightness,                  # brightness %
        0x00, 0x00,                 # speed, direction
        0xF0,                       # constant
        csum
    ])


def zengge_set_effect(effect_num, speed=50, brightness=100):
    """Zengge protocol: set effect/symphony mode (strip firmware style)"""
    c = next_counter()
    csum = (0x42 + effect_num + speed + brightness) & 0xFF
    return bytes([
        (c >> 8) & 0xFF, c & 0xFF,
        0x80, 0x00,
        0x00, 0x05, 0x06,
        0x0B, 0x42,                 # effect command
        effect_num,                 # 0x01 - 0x64
        speed,                      # 0x01 - 0x64
        brightness,                 # 0x01 - 0x64
        csum
    ])


def zengge_query_status():
    """Request device status notification"""
    c = next_counter()
    return bytes([
        (c >> 8) & 0xFF, c & 0xFF,
        0x80, 0x00,
        0x00, 0x04, 0x05,
        0x0A, 0x81, 0x8A, 0x8B, 0x96
    ])


# ─── iDotMatrix-style commands (simpler protocol) ────────────────────────────

def idot_power_on():
    return bytes([0x05, 0x00, 0x07, 0x01, 0x01])

def idot_power_off():
    return bytes([0x05, 0x00, 0x07, 0x01, 0x00])

def idot_graffiti_pixel(x, y, r, g, b):
    return bytes([0x0A, 0x00, 0x05, 0x01, 0x00, r, g, b, x, y])


# ─── Simple raw test payloads ────────────────────────────────────────────────

SIMPLE_TESTS = [
    ("all-zeros (4 bytes)", bytes([0x00, 0x00, 0x00, 0x00])),
    ("0x01 x4",             bytes([0x01, 0x01, 0x01, 0x01])),
    ("0xFF x4",             bytes([0xFF, 0xFF, 0xFF, 0xFF])),
]


# ─── Notification handler ────────────────────────────────────────────────────

def make_notification_handler(label):
    def handler(sender, data: bytearray):
        print(f"  << NOTIFY [{label}] ({len(data)} bytes): {data.hex()}")
        try:
            text = data.decode("utf-8", errors="replace")
            if any(c.isalpha() for c in text):
                print(f"     (text): {text}")
        except Exception:
            pass
    return handler


async def find_device():
    print(f"Scanning for '{TARGET_NAME}' ...")
    devices = await BleakScanner.discover(timeout=SCAN_DURATION, return_adv=True)
    for addr, (dev, adv) in devices.items():
        name = dev.name or adv.local_name or ""
        if TARGET_NAME.lower() in name.lower():
            print(f"Found: {name}  ({addr})  RSSI={adv.rssi}")
            return dev
    return None


async def try_write(client, char_uuid, handle, data, label):
    """Try writing data to a characteristic, return True on success."""
    try:
        await client.write_gatt_char(handle, data, response=False)
        print(f"  >> WRITE [{label}] handle={handle}: {data.hex()}")
        await asyncio.sleep(1.0)
        return True
    except Exception as e:
        print(f"  !! WRITE [{label}] handle={handle} FAILED: {e}")
        return False


async def main():
    dev = await find_device()
    if not dev:
        print(f"Could not find '{TARGET_NAME}'.")
        sys.exit(1)

    print(f"\nConnecting to {dev.name} ({dev.address}) ...")
    async with BleakClient(dev) as client:
        print(f"Connected: {client.is_connected}\n")

        # Subscribe to all notify characteristics
        print("Subscribing to notifications ...")
        try:
            await client.start_notify(7, make_notification_handler("ae02/h7"))
        except Exception as e:
            print(f"  Could not subscribe to handle 7: {e}")
        try:
            await client.start_notify(12, make_notification_handler("ae04/h12"))
        except Exception as e:
            print(f"  Could not subscribe to handle 12: {e}")
        try:
            await client.start_notify(67, make_notification_handler("ae3c/h67"))
        except Exception as e:
            print(f"  Could not subscribe to handle 67: {e}")
        try:
            await client.start_notify(131, make_notification_handler("ae02/h131"))
        except Exception as e:
            print(f"  Could not subscribe to handle 131: {e}")

        await asyncio.sleep(1.0)

        # ── Read ae10 config register ────────────────────────────────────
        print("\n" + "=" * 60)
        print("STEP 1: Read config register ae10 (handle 18)")
        print("=" * 60)
        try:
            val = await client.read_gatt_char(18)
            print(f"  ae10 value: {val.hex()}")
        except Exception as e:
            print(f"  Failed: {e}")

        # ── Try Zengge-style status query ────────────────────────────────
        print("\n" + "=" * 60)
        print("STEP 2: Zengge status query (ae01, handle 5)")
        print("=" * 60)
        await try_write(client, WRITE_CHAR_UUID, 5, zengge_query_status(), "status-query")
        await asyncio.sleep(2.0)

        # ── Try iDotMatrix-style power on ────────────────────────────────
        print("\n" + "=" * 60)
        print("STEP 3: iDotMatrix-style power ON")
        print("=" * 60)
        for handle in [5, 10, 65, 129]:
            await try_write(client, None, handle, idot_power_on(), f"idot-on/h{handle}")

        # ── Try Zengge-style power on ────────────────────────────────────
        print("\n" + "=" * 60)
        print("STEP 4: Zengge-style power ON")
        print("=" * 60)
        await try_write(client, WRITE_CHAR_UUID, 5, zengge_power_on(), "zengge-on")

        # ── Try setting RED ──────────────────────────────────────────────
        print("\n" + "=" * 60)
        print("STEP 5: Set colour RED")
        print("=" * 60)
        await try_write(client, WRITE_CHAR_UUID, 5, zengge_set_rgb(0xFF, 0x00, 0x00), "red")
        await asyncio.sleep(2.0)

        # ── Try setting GREEN ────────────────────────────────────────────
        print("\n" + "=" * 60)
        print("STEP 6: Set colour GREEN")
        print("=" * 60)
        await try_write(client, WRITE_CHAR_UUID, 5, zengge_set_rgb(0x00, 0xFF, 0x00), "green")
        await asyncio.sleep(2.0)

        # ── Try setting BLUE ─────────────────────────────────────────────
        print("\n" + "=" * 60)
        print("STEP 7: Set colour BLUE")
        print("=" * 60)
        await try_write(client, WRITE_CHAR_UUID, 5, zengge_set_rgb(0x00, 0x00, 0xFF), "blue")
        await asyncio.sleep(2.0)

        # ── Try effect #1 ────────────────────────────────────────────────
        print("\n" + "=" * 60)
        print("STEP 8: Set effect #1 (rainbow or similar)")
        print("=" * 60)
        await try_write(client, WRITE_CHAR_UUID, 5, zengge_set_effect(0x01), "effect-1")
        await asyncio.sleep(3.0)

        # ── Try effect #5 ────────────────────────────────────────────────
        print("\n" + "=" * 60)
        print("STEP 9: Set effect #5")
        print("=" * 60)
        await try_write(client, WRITE_CHAR_UUID, 5, zengge_set_effect(0x05), "effect-5")
        await asyncio.sleep(3.0)

        # ── Try writing same commands to handle 10 (ae03) ────────────────
        print("\n" + "=" * 60)
        print("STEP 10: Repeat RED on ae03 (handle 10) — alt data channel")
        print("=" * 60)
        await try_write(client, WRITE2_CHAR_UUID, 10, zengge_set_rgb(0xFF, 0x00, 0x00), "red/h10")
        await asyncio.sleep(2.0)

        # ── Try writing to service ae3a (handle 65) ──────────────────────
        print("\n" + "=" * 60)
        print("STEP 11: Repeat RED on ae3b (handle 65) — service 2")
        print("=" * 60)
        await try_write(client, WRITE3_CHAR_UUID, 65, zengge_set_rgb(0xFF, 0x00, 0x00), "red/h65")
        await asyncio.sleep(2.0)

        # ── Try writing to service ae00 (handle 129) ─────────────────────
        print("\n" + "=" * 60)
        print("STEP 12: Repeat RED on ae01 (handle 129) — service 3")
        print("=" * 60)
        await try_write(client, WRITE4_CHAR_UUID, 129, zengge_set_rgb(0xFF, 0x00, 0x00), "red/h129")
        await asyncio.sleep(2.0)

        # ── Power off ────────────────────────────────────────────────────
        print("\n" + "=" * 60)
        print("STEP 13: Zengge-style power OFF")
        print("=" * 60)
        await try_write(client, WRITE_CHAR_UUID, 5, zengge_power_off(), "zengge-off")

        # ── iDotMatrix-style power off ───────────────────────────────────
        print("\n" + "=" * 60)
        print("STEP 14: iDotMatrix-style power OFF")
        print("=" * 60)
        for handle in [5, 10, 65, 129]:
            await try_write(client, None, handle, idot_power_off(), f"idot-off/h{handle}")

        await asyncio.sleep(2.0)
        print("\n" + "=" * 60)
        print("DONE. Check which steps caused a visible change on the device!")
        print("=" * 60)
        print("""
Look for:
  - Did any step make the LEDs turn on/off?
  - Did any step change the colour?
  - Did any step trigger an animation/effect?
  - Did any notifications come back (printed above as '<< NOTIFY')?

Report back what you observed and we'll narrow down the protocol.
""")


if __name__ == "__main__":
    asyncio.run(main())
