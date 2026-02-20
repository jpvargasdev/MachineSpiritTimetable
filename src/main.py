#!/usr/bin/env python3
"""XyaoLED interactive controller.

Usage:
    python -m src.main

Commands: on, off, text <message>, color <r> <g> <b>, speed <n>, quit
"""

import asyncio

from device import XyaoLED

DEVICE_ADDRESS = "01DC102F-B8D9-1ACB-2353-441F394DA3A3"


def on_notification(sender, data: bytearray):
    print(f"  <- {data.hex()}")


async def main():
    device = XyaoLED(DEVICE_ADDRESS)
    device.on_notify(on_notification)

    await device.connect()

    color = (255, 0, 0)  # default red
    speed = 60

    print("\nCommands:")
    print("  on              - turn display on")
    print("  off             - turn display off")
    print("  text <message>  - display scrolling text")
    print("  color <r> <g> <b> - set text color (0-255)")
    print("  speed <n>       - set scroll speed (1-255)")
    print("  quit            - disconnect and exit")
    print()

    loop = asyncio.get_event_loop()
    try:
        while device.is_connected:
            line = await loop.run_in_executor(None, input, "> ")
            parts = line.strip().split()

            if not parts:
                continue

            cmd = parts[0].lower()

            if cmd == "on":
                await device.on()
            elif cmd == "off":
                await device.off()
            elif cmd == "text" and len(parts) > 1:
                text = " ".join(parts[1:])
                await device.send_text(text, color=color, speed=speed)
            elif cmd == "color" and len(parts) == 4:
                try:
                    color = (int(parts[1]), int(parts[2]), int(parts[3]))
                    print(f"  Color set to {color}")
                except ValueError:
                    print("  Usage: color <r> <g> <b>  (values 0-255)")
            elif cmd == "speed" and len(parts) == 2:
                try:
                    speed = int(parts[1])
                    print(f"  Speed set to {speed}")
                except ValueError:
                    print("  Usage: speed <n>  (1-255)")
            elif cmd in ("quit", "q", "exit"):
                break
            else:
                print(f"  Unknown: {line.strip()}")
    except (EOFError, KeyboardInterrupt):
        pass

    await device.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
