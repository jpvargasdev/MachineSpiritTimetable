"""XyaoLED device - high-level API."""

import asyncio
from connection import Connection
import commands
from font import render_text


class XyaoLED:
    def __init__(self, address: str):
        self.address = address
        self.conn = Connection(address)
        self._seq = 0x01

    def _next_seq(self) -> int:
        seq = self._seq
        self._seq = (self._seq + 1) & 0xFF
        return seq

    def on_notify(self, callback):
        """Register a notification callback: callback(sender, data)."""
        self.conn.on_notify(callback)

    async def connect(self):
        """Connect to the LED device."""
        connected = await self.conn.connect()
        if connected:
            print(f"Connected to {self.address}")
        return connected

    async def disconnect(self):
        """Disconnect from the device."""
        await self.conn.disconnect()
        print("Disconnected.")

    @property
    def is_connected(self) -> bool:
        return self.conn.is_connected

    async def send(self, data: bytes):
        """Send raw bytes to the device."""
        await self.conn.write(data)

    async def on(self):
        """Turn the LED matrix ON."""
        cmd = commands.on_cmd(self._next_seq())
        await self.send(cmd)
        print("ON")

    async def off(self):
        """Turn the LED matrix OFF."""
        cmd = commands.off_cmd(self._next_seq())
        await self.send(cmd)
        print("OFF")

    async def send_text(self, text: str, color: tuple = (255, 0, 0),
                        speed: int = 60):
        """Display scrolling text on the LED matrix.

        Sends the 4-packet sequence:
          1. Clear/prepare display
          2. Init text transfer
          3. Bitmap data (rendered text)
          4. Activate display

        Args:
            text: Text to display (ASCII, will be uppercased).
            color: (R, G, B) foreground color tuple. Default red.
            speed: Scroll speed (1-255, default 60).
        """
        bitmap = render_text(text)

        # Step 1: Clear display
        await self.send(commands.clear_cmd(self._next_seq()))
        await asyncio.sleep(0.05)

        # Step 2: Init text transfer
        await self.send(commands.text_init_cmd(self._next_seq()))
        await asyncio.sleep(0.05)

        # Step 3: Send bitmap data
        await self.send(commands.text_data_cmd(
            self._next_seq(), bitmap, fg_color=color, speed=speed
        ))
        await asyncio.sleep(0.05)

        # Step 4: Activate display (text/animation mode)
        await self.send(commands.activate_cmd(self._next_seq()))

        print(f"TEXT: {text!r} (color={color}, speed={speed})")

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, *args):
        await self.disconnect()
