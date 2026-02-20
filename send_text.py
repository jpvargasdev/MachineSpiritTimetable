#!/usr/bin/env python3
"""Send arbitrary text to XyaoLED device via Preview mode.

Usage:
    python3 send_text.py "Hello World"
    python3 send_text.py "Hello" --color red
    python3 send_text.py "Test" --color blue --size large
    python3 send_text.py "Hi" --color green
    python3 send_text.py "ABC" --preview   # just show ASCII art, don't send

The text is rendered using a built-in 5x7 bitmap font (with optional 2x
scaling for large size), split into 32-column pages, and sent using the
Preview protocol (3 commands: handshake, text_init, bitmap).
"""

import argparse
import asyncio
import struct
import sys

from bleak import BleakClient

# ── Device constants ──────────────────────────────────────────────────
DEVICE_ADDRESS = "01DC102F-B8D9-1ACB-2353-441F394DA3A3"
WRITE_HANDLE = 129
NOTIFY_HANDLE = 131

MAGIC = bytes.fromhex("99aa002eff88")

# ── 5x7 bitmap font ──────────────────────────────────────────────────
# Each char: 7 rows, each row is N bits wide (MSB = leftmost pixel).
# Width varies per character for proportional feel (most are 5px).
# Uppercase chars are wider (6-7px) to better fill the 16-row display.

# Standard 5x7 font - each glyph is (width, [7 rows])
# Row values: MSB = leftmost pixel within the glyph
FONT = {
    # ── Uppercase (mostly 5-wide, some 6) ──
    'A': (5, [0x0E, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11]),
    'B': (5, [0x1E, 0x11, 0x11, 0x1E, 0x11, 0x11, 0x1E]),
    'C': (5, [0x0E, 0x11, 0x10, 0x10, 0x10, 0x11, 0x0E]),
    'D': (5, [0x1E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x1E]),
    'E': (5, [0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x1F]),
    'F': (5, [0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x10]),
    'G': (5, [0x0E, 0x11, 0x10, 0x17, 0x11, 0x11, 0x0E]),
    'H': (5, [0x11, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11]),
    'I': (3, [0x07, 0x02, 0x02, 0x02, 0x02, 0x02, 0x07]),
    'J': (5, [0x07, 0x02, 0x02, 0x02, 0x02, 0x12, 0x0C]),
    'K': (5, [0x11, 0x12, 0x14, 0x18, 0x14, 0x12, 0x11]),
    'L': (5, [0x10, 0x10, 0x10, 0x10, 0x10, 0x10, 0x1F]),
    'M': (5, [0x11, 0x1B, 0x15, 0x15, 0x11, 0x11, 0x11]),
    'N': (5, [0x11, 0x19, 0x15, 0x13, 0x11, 0x11, 0x11]),
    'O': (5, [0x0E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E]),
    'P': (5, [0x1E, 0x11, 0x11, 0x1E, 0x10, 0x10, 0x10]),
    'Q': (5, [0x0E, 0x11, 0x11, 0x11, 0x15, 0x12, 0x0D]),
    'R': (5, [0x1E, 0x11, 0x11, 0x1E, 0x14, 0x12, 0x11]),
    'S': (5, [0x0E, 0x11, 0x10, 0x0E, 0x01, 0x11, 0x0E]),
    'T': (5, [0x1F, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04]),
    'U': (5, [0x11, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E]),
    'V': (5, [0x11, 0x11, 0x11, 0x11, 0x11, 0x0A, 0x04]),
    'W': (5, [0x11, 0x11, 0x11, 0x15, 0x15, 0x15, 0x0A]),
    'X': (5, [0x11, 0x11, 0x0A, 0x04, 0x0A, 0x11, 0x11]),
    'Y': (5, [0x11, 0x11, 0x0A, 0x04, 0x04, 0x04, 0x04]),
    'Z': (5, [0x1F, 0x01, 0x02, 0x04, 0x08, 0x10, 0x1F]),
    # ── Lowercase ──
    'a': (5, [0x00, 0x00, 0x0E, 0x01, 0x0F, 0x11, 0x0F]),
    'b': (5, [0x10, 0x10, 0x1E, 0x11, 0x11, 0x11, 0x1E]),
    'c': (5, [0x00, 0x00, 0x0E, 0x11, 0x10, 0x11, 0x0E]),
    'd': (5, [0x01, 0x01, 0x0F, 0x11, 0x11, 0x11, 0x0F]),
    'e': (5, [0x00, 0x00, 0x0E, 0x11, 0x1F, 0x10, 0x0E]),
    'f': (4, [0x06, 0x08, 0x0E, 0x08, 0x08, 0x08, 0x08]),
    'g': (5, [0x00, 0x00, 0x0F, 0x11, 0x0F, 0x01, 0x0E]),
    'h': (5, [0x10, 0x10, 0x1E, 0x11, 0x11, 0x11, 0x11]),
    'i': (3, [0x02, 0x00, 0x06, 0x02, 0x02, 0x02, 0x07]),
    'j': (4, [0x02, 0x00, 0x06, 0x02, 0x02, 0x0A, 0x0C]),
    'k': (5, [0x10, 0x10, 0x12, 0x14, 0x18, 0x14, 0x12]),
    'l': (3, [0x06, 0x02, 0x02, 0x02, 0x02, 0x02, 0x07]),
    'm': (5, [0x00, 0x00, 0x1A, 0x15, 0x15, 0x11, 0x11]),
    'n': (5, [0x00, 0x00, 0x1E, 0x11, 0x11, 0x11, 0x11]),
    'o': (5, [0x00, 0x00, 0x0E, 0x11, 0x11, 0x11, 0x0E]),
    'p': (5, [0x00, 0x00, 0x1E, 0x11, 0x1E, 0x10, 0x10]),
    'q': (5, [0x00, 0x00, 0x0F, 0x11, 0x0F, 0x01, 0x01]),
    'r': (5, [0x00, 0x00, 0x16, 0x19, 0x10, 0x10, 0x10]),
    's': (5, [0x00, 0x00, 0x0F, 0x10, 0x0E, 0x01, 0x1E]),
    't': (4, [0x08, 0x08, 0x0E, 0x08, 0x08, 0x09, 0x06]),
    'u': (5, [0x00, 0x00, 0x11, 0x11, 0x11, 0x11, 0x0E]),
    'v': (5, [0x00, 0x00, 0x11, 0x11, 0x11, 0x0A, 0x04]),
    'w': (5, [0x00, 0x00, 0x11, 0x11, 0x15, 0x15, 0x0A]),
    'x': (5, [0x00, 0x00, 0x11, 0x0A, 0x04, 0x0A, 0x11]),
    'y': (5, [0x00, 0x00, 0x11, 0x11, 0x0F, 0x01, 0x0E]),
    'z': (5, [0x00, 0x00, 0x1F, 0x02, 0x04, 0x08, 0x1F]),
    # ── Digits ──
    '0': (5, [0x0E, 0x11, 0x13, 0x15, 0x19, 0x11, 0x0E]),
    '1': (3, [0x02, 0x06, 0x02, 0x02, 0x02, 0x02, 0x07]),
    '2': (5, [0x0E, 0x11, 0x01, 0x06, 0x08, 0x10, 0x1F]),
    '3': (5, [0x0E, 0x11, 0x01, 0x06, 0x01, 0x11, 0x0E]),
    '4': (5, [0x02, 0x06, 0x0A, 0x12, 0x1F, 0x02, 0x02]),
    '5': (5, [0x1F, 0x10, 0x1E, 0x01, 0x01, 0x11, 0x0E]),
    '6': (5, [0x06, 0x08, 0x10, 0x1E, 0x11, 0x11, 0x0E]),
    '7': (5, [0x1F, 0x01, 0x02, 0x04, 0x08, 0x08, 0x08]),
    '8': (5, [0x0E, 0x11, 0x11, 0x0E, 0x11, 0x11, 0x0E]),
    '9': (5, [0x0E, 0x11, 0x11, 0x0F, 0x01, 0x02, 0x0C]),
    # ── Punctuation ──
    ' ': (3, [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]),
    '!': (1, [0x01, 0x01, 0x01, 0x01, 0x01, 0x00, 0x01]),
    '.': (1, [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x01]),
    ',': (2, [0x00, 0x00, 0x00, 0x00, 0x00, 0x01, 0x02]),
    ':': (1, [0x00, 0x00, 0x01, 0x00, 0x01, 0x00, 0x00]),
    '-': (3, [0x00, 0x00, 0x00, 0x07, 0x00, 0x00, 0x00]),
    '_': (5, [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x1F]),
    '?': (5, [0x0E, 0x11, 0x01, 0x02, 0x04, 0x00, 0x04]),
    '/': (3, [0x01, 0x01, 0x02, 0x02, 0x02, 0x04, 0x04]),
    '(': (3, [0x01, 0x02, 0x04, 0x04, 0x04, 0x02, 0x01]),
    ')': (3, [0x04, 0x02, 0x01, 0x01, 0x01, 0x02, 0x04]),
    '+': (5, [0x00, 0x04, 0x04, 0x1F, 0x04, 0x04, 0x00]),
    '=': (5, [0x00, 0x00, 0x1F, 0x00, 0x1F, 0x00, 0x00]),
    '#': (5, [0x0A, 0x0A, 0x1F, 0x0A, 0x1F, 0x0A, 0x0A]),
    '@': (5, [0x0E, 0x11, 0x17, 0x15, 0x17, 0x10, 0x0E]),
    '<': (3, [0x01, 0x02, 0x04, 0x02, 0x01, 0x00, 0x00]),
    '>': (3, [0x04, 0x02, 0x01, 0x02, 0x04, 0x00, 0x00]),
    '*': (5, [0x00, 0x04, 0x15, 0x0E, 0x15, 0x04, 0x00]),
    "'": (1, [0x01, 0x01, 0x00, 0x00, 0x00, 0x00, 0x00]),
    '"': (3, [0x05, 0x05, 0x00, 0x00, 0x00, 0x00, 0x00]),
}

CHAR_SPACING = 2  # pixels between characters (1x)
LEFT_MARGIN = 2   # left margin on each page
FONT_HEIGHT = 7
DISPLAY_ROWS = 16
PAGE_WIDTH = 32   # bits per page

# Vertical offsets per scale to center the font in 16 rows:
#   1x: 7 rows tall  -> offset 4 (rows 4-10, 4 above + 2 below)
#   2x: 14 rows tall -> offset 1 (rows 1-14, 1 above + 1 below)
V_OFFSETS = {1: 4, 2: 1}


# ── Color presets ─────────────────────────────────────────────────────
COLORS = {
    'red':     (0xFF, 0x00, 0x00),
    'green':   (0x00, 0xFF, 0x00),
    'blue':    (0x00, 0x00, 0xFF),
    'yellow':  (0xFF, 0xFF, 0x00),
    'cyan':    (0x00, 0xFF, 0xFF),
    'magenta': (0xFF, 0x00, 0xFF),
    'white':   (0xFF, 0xFF, 0xFF),
}


# ── Bitmap rendering ─────────────────────────────────────────────────

def render_text_to_pages(text: str, scale: int = 1) -> list[list[int]]:
    """Render text into a list of pages, each page = list of 16 uint32 rows.

    Bit ordering: LSB (bit 0) = leftmost column, as required by the device.
    Each page is 32 columns wide. Characters are placed left-to-right with
    a left margin and inter-character spacing.

    Args:
        text: Text to render
        scale: 1 = small (5x7), 2 = large (10x14, 2x scaled)

    Returns:
        List of pages. Each page is a list of 16 uint32 values.
    """
    # Get glyph data for each character
    glyphs = []
    for ch in text:
        if ch in FONT:
            glyphs.append(FONT[ch])
        else:
            glyphs.append(FONT.get(' ', (3, [0]*7)))

    if not glyphs:
        return [[0] * DISPLAY_ROWS]

    char_spacing = CHAR_SPACING * scale
    left_margin = LEFT_MARGIN

    # Split glyphs into pages that fit within PAGE_WIDTH columns
    pages = []
    current_page_glyphs = []
    current_width = left_margin

    for glyph in glyphs:
        gw = glyph[0] * scale  # scaled glyph width
        needed = gw + (char_spacing if current_page_glyphs else 0)
        if current_width + needed > PAGE_WIDTH and current_page_glyphs:
            # This glyph doesn't fit - flush current page
            pages.append(_render_page(current_page_glyphs, scale))
            current_page_glyphs = []
            current_width = left_margin
        if current_page_glyphs:
            current_width += char_spacing
        current_page_glyphs.append(glyph)
        current_width += gw

    # Flush last page
    if current_page_glyphs:
        pages.append(_render_page(current_page_glyphs, scale))

    return pages


def _render_page(glyphs: list[tuple[int, list[int]]], scale: int = 1) -> list[int]:
    """Render a list of glyphs into a single 32-column page.

    Args:
        glyphs: List of (width, [7 rows]) tuples
        scale: 1 = normal, 2 = double each pixel

    Returns list of 16 uint32 values (LSB = leftmost column).
    """
    rows = [0] * DISPLAY_ROWS
    v_offset = V_OFFSETS.get(scale, 4)
    char_spacing = CHAR_SPACING * scale
    col = LEFT_MARGIN  # current column position

    for glyph_width, glyph_rows in glyphs:
        for font_row_idx in range(FONT_HEIGHT):
            glyph_val = glyph_rows[font_row_idx]
            for sy in range(scale):
                display_row = v_offset + font_row_idx * scale + sy
                if display_row >= DISPLAY_ROWS:
                    break
                # glyph_val: MSB = leftmost pixel within glyph
                for bit in range(glyph_width):
                    if glyph_val & (1 << (glyph_width - 1 - bit)):
                        for sx in range(scale):
                            pixel_col = col + bit * scale + sx
                            if pixel_col < PAGE_WIDTH:
                                rows[display_row] |= (1 << pixel_col)
        col += glyph_width * scale + char_spacing

    return rows


def pages_to_ascii(pages: list[list[int]]) -> str:
    """Convert pages to ASCII art for preview."""
    lines = []
    for page_idx, page in enumerate(pages):
        lines.append(f"Page {page_idx} ({PAGE_WIDTH} cols):")
        for row_idx, row_val in enumerate(page):
            bits = ''
            for col in range(PAGE_WIDTH):
                bits += '#' if (row_val >> col) & 1 else '.'
            hex_bytes = struct.pack('<I', row_val).hex()
            lines.append(f"  Row {row_idx:2d}: {bits}  {hex_bytes}")
        lines.append("")
    return '\n'.join(lines)


# ── Protocol packet builders ─────────────────────────────────────────

def build_handshake() -> bytes:
    """Build a handshake packet (cmd 0x00, 31 bytes).

    We reuse a captured handshake since replays work fine.
    The device doesn't verify the timestamp/hash.
    """
    return bytes.fromhex(
        "99aa002eff881f00000001001a02140f1b02050100435897dc6dd500000000"
    )


def build_text_init(sub: int = 0x03, seq: int = 0x02) -> bytes:
    """Build a text_init packet (cmd 0x04, 13 bytes).

    Args:
        sub: Slot ID (default 0x03, matching captured packets)
        seq: Sequence number
    """
    pkt = MAGIC + bytes([0x0D, 0x00, 0x04, sub, seq, 0xFF, 0x00])
    return pkt


def build_bitmap(pages: list[list[int]], color: tuple[int, int, int],
                 sub: int = 0x03, seq: int = 0x02,
                 brightness: int = 0xFF, speed: int = 0x3C) -> bytes:
    """Build a bitmap packet (cmd 0x07, variable size).

    Args:
        pages: List of pages, each page = list of 16 uint32 row values
        color: (R, G, B) tuple, each 0x00 or 0xFF
        sub: Slot ID (must match text_init)
        seq: Sequence number (must match text_init)
        brightness: Brightness value (default 0xFF)
        speed: Scroll speed (default 0x3C = 60)

    Returns:
        Complete bitmap packet bytes
    """
    num_pages = len(pages)
    bitmap_data_len = 12 + (num_pages * 64)
    total_packet_size = 36 + (num_pages * 64)

    r, g, b = color

    # Build packet
    pkt = bytearray(MAGIC)

    # Length byte - for packets > 255 bytes this is just the low byte
    # (the device seems to handle this based on actual BLE packet size)
    pkt.append(total_packet_size & 0xFF)
    pkt.append(0x00)       # [7] always 0x00
    pkt.append(0x07)       # [8] CMD = bitmap
    pkt.append(sub)        # [9] SUB
    pkt.append(seq)        # [10] SEQ

    # Metadata (25 bytes, offsets 11-35)
    pkt.extend(struct.pack('<H', bitmap_data_len))  # [11-12] bitmap_data_len LE
    pkt.append(0x00)       # [13]
    pkt.append(0x02)       # [14]
    pkt.append(0x00)       # [15]
    pkt.append(0x02)       # [16]
    pkt.append(0x01)       # [17]
    pkt.append(0x00)       # [18]
    pkt.append(0x00)       # [19]
    pkt.append(num_pages)  # [20] page count
    pkt.append(0x00)       # [21]
    pkt.append(0x03)       # [22] animation mode?
    pkt.append(0x00)       # [23]
    pkt.append(0x00)       # [24]
    pkt.append(0x00)       # [25]
    pkt.append(0x00)       # [26]
    pkt.append(r)          # [27] RED
    pkt.append(g)          # [28] GREEN
    pkt.append(b)          # [29] BLUE
    pkt.append(0x00)       # [30]
    pkt.append(0x00)       # [31]
    pkt.append(brightness) # [32] brightness
    pkt.append(0x00)       # [33]
    pkt.append(speed)      # [34] speed
    pkt.append(0x00)       # [35]

    # Pixel data (offset 36+)
    for page in pages:
        for row_val in page:
            pkt.extend(struct.pack('<I', row_val & 0xFFFFFFFF))

    assert len(pkt) == total_packet_size, \
        f"Packet size mismatch: got {len(pkt)}, expected {total_packet_size}"
    return bytes(pkt)


# ── BLE send logic ───────────────────────────────────────────────────

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


async def send_packet(client, label, pkt):
    """Send a packet and wait for notification response."""
    print(f"\n--- {label} ({len(pkt)} bytes) ---")
    print(f"  -> {pkt.hex()}")
    await client.write_gatt_char(WRITE_HANDLE, pkt, response=False)
    resp = await wait_for_notify(3.0)
    return resp


async def send_text(text: str, color: tuple[int, int, int] = (0xFF, 0x00, 0x00),
                    preview_only: bool = False, scale: int = 1):
    """Render text and send to device via Preview mode.

    Args:
        text: Text to display
        color: (R, G, B) color tuple
        preview_only: If True, just show ASCII art, don't send
        scale: 1 = small (5x7), 2 = large (10x14)
    """
    # Render
    pages = render_text_to_pages(text, scale=scale)
    size_label = "small (5x7)" if scale == 1 else f"large ({scale}x scaled)"
    print(f"Text: '{text}'")
    print(f"Color: R={color[0]:02X} G={color[1]:02X} B={color[2]:02X}")
    print(f"Size: {size_label}")
    print(f"Pages: {len(pages)}")
    print()
    print(pages_to_ascii(pages))

    if preview_only:
        return

    # Build packets
    handshake = build_handshake()
    text_init = build_text_init(sub=0x03, seq=0x02)
    bitmap = build_bitmap(pages, color, sub=0x03, seq=0x02)

    print(f"Bitmap packet: {len(bitmap)} bytes")
    print()

    # Send
    print(f"Connecting to XyaoLED_44BF...")
    async with BleakClient(DEVICE_ADDRESS) as client:
        print(f"Connected: {client.is_connected}, MTU: {client.mtu_size}")
        await client.start_notify(NOTIFY_HANDLE, notification_handler)
        await asyncio.sleep(0.5)

        await send_packet(client, "Handshake", handshake)
        await send_packet(client, "Text init", text_init)
        await send_packet(client, "Bitmap", bitmap)
        # Wait for second notification (command complete)
        await wait_for_notify(3.0)

        print(f"\n=== Sent '{text}' — check device! ===")
        print("Waiting 10s before disconnect...")
        await asyncio.sleep(10)
        await client.stop_notify(NOTIFY_HANDLE)

    print("Disconnected.")


# ── CLI ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Send text to XyaoLED device")
    parser.add_argument("text", help="Text to display")
    parser.add_argument("--color", "-c", default="red",
                        choices=list(COLORS.keys()),
                        help="Color (default: red)")
    parser.add_argument("--size", "-s", default="small",
                        choices=["small", "large"],
                        help="Font size: small (5x7) or large (10x14, 2x scaled)")
    parser.add_argument("--preview", "-p", action="store_true",
                        help="Preview only (don't send to device)")
    args = parser.parse_args()

    color = COLORS[args.color]
    scale = 2 if args.size == "large" else 1
    asyncio.run(send_text(args.text, color, preview_only=args.preview, scale=scale))


if __name__ == "__main__":
    main()
