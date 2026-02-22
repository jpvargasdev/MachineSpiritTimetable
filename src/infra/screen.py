"""Screen - high-level API for XyaoLED display."""

from .ble_client import BLEClient, DEFAULT_ADDRESS
from .bitmap import render_text_to_pages, render_two_lines, parse_color, pages_to_ascii
from .protocol import build_handshake, build_text_init, build_bitmap


class Screen:
    """High-level interface for XyaoLED LED matrix display.
    
    Usage:
        async with Screen() as screen:
            await screen.render("Hello World", color="red", scroll=True)
    """
    
    def __init__(self, address: str = DEFAULT_ADDRESS):
        """Initialize Screen with device address.
        
        Args:
            address: BLE device address (default: XyaoLED_44BF)
        """
        self.address = address
        self._client = BLEClient(address)
    
    async def connect(self) -> bool:
        """Connect to the LED display."""
        return await self._client.connect()
    
    async def disconnect(self):
        """Disconnect from the LED display."""
        await self._client.disconnect()
    
    @property
    def is_connected(self) -> bool:
        """Check if connected to display."""
        return self._client.is_connected
    
    async def render(
        self,
        text: str,
        color: str | tuple[int, int, int] = "red",
        scroll: bool = False,
        speed: int = 60,
        brightness: int = 255,
        scale: int = 1,
        preview: bool = False
    ) -> str | None:
        """Render text on the LED display.
        
        Args:
            text: Text to display
            color: Color name ('red', 'green', 'blue', etc.) or (R, G, B) tuple
            scroll: Enable scrolling animation
            speed: Scroll speed (1-255, default 60)
            brightness: Brightness (0-255, default 255)
            scale: Font scale (1 = small 5x7, 2 = large 10x14)
            preview: If True, return ASCII art preview without sending
            
        Returns:
            ASCII art preview if preview=True, else None
        """
        # Parse color
        rgb = parse_color(color)
        
        # Render text to bitmap pages
        pages = render_text_to_pages(text, scale=scale)
        
        # Preview mode - just return ASCII art
        if preview:
            return pages_to_ascii(pages)
        
        # Build protocol packets
        handshake = build_handshake()
        text_init = build_text_init(sub=0x03, seq=0x02)
        bitmap = build_bitmap(
            pages, rgb,
            sub=0x03, seq=0x02,
            brightness=brightness,
            speed=speed,
            scroll=scroll
        )
        
        # Send to device
        await self._client.write(handshake)
        await self._client.write(text_init)
        await self._client.write(bitmap)
        
        return None
    
    async def render_two_lines(
        self,
        line1: str,
        line2: str,
        color: str | tuple[int, int, int] = "red",
        scroll: bool = False,
        speed: int = 60,
        brightness: int = 255,
        use_medium: bool = False,
        preview: bool = False
    ) -> str | None:
        """Render two lines of text on the LED display.
        
        Uses a smaller font to fit both lines in the 16-row display.
        Line 1 appears at top, line 2 at bottom.
        
        Args:
            line1: First line (top)
            line2: Second line (bottom)
            color: Color name or (R, G, B) tuple
            scroll: Enable scrolling animation
            speed: Scroll speed (1-255, default 60)
            brightness: Brightness (0-255, default 255)
            use_medium: Use medium font (5x6) instead of small (3x5)
            preview: If True, return ASCII art preview without sending
            
        Returns:
            ASCII art preview if preview=True, else None
        """
        # Parse color
        rgb = parse_color(color)
        
        # Render two lines to single page
        pages = render_two_lines(line1, line2, use_medium=use_medium)
        
        # Preview mode
        if preview:
            return pages_to_ascii(pages)
        
        # Build protocol packets
        handshake = build_handshake()
        text_init = build_text_init(sub=0x03, seq=0x02)
        bitmap = build_bitmap(
            pages, rgb,
            sub=0x03, seq=0x02,
            brightness=brightness,
            speed=speed,
            scroll=scroll
        )
        
        # Send to device
        await self._client.write(handshake)
        await self._client.write(text_init)
        await self._client.write(bitmap)
        
        return None
    
    async def __aenter__(self):
        await self.connect()
        return self
    
    async def __aexit__(self, *args):
        await self.disconnect()
