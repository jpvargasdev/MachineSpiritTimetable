"""XyaoLED BLE protocol - packet builders for device communication."""

import struct


# Protocol constants
MAGIC = bytes.fromhex("99aa002eff88")


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
    return MAGIC + bytes([0x0D, 0x00, 0x04, sub, seq, 0xFF, 0x00])


def build_bitmap(pages: list[list[int]], color: tuple[int, int, int],
                 sub: int = 0x03, seq: int = 0x02,
                 brightness: int = 0xFF, speed: int = 0x3C,
                 scroll: bool = False) -> bytes:
    """Build a bitmap packet (cmd 0x07, variable size).

    Args:
        pages: List of pages, each page = list of 16 uint32 row values
        color: (R, G, B) tuple, each 0x00 or 0xFF
        sub: Slot ID (must match text_init)
        seq: Sequence number (must match text_init)
        brightness: Brightness value (default 0xFF)
        speed: Scroll speed (default 0x3C = 60)
        scroll: Enable scrolling animation (default False = static)

    Returns:
        Complete bitmap packet bytes
    """
    num_pages = len(pages)
    bitmap_data_len = 12 + (num_pages * 64)
    total_packet_size = 36 + (num_pages * 64)

    r, g, b = color
    
    # Scroll control (discovered from HCI capture Feb 22, 2026)
    # offset 22: mode (0x00 = scroll, 0x03 = static)
    # offset 33: scroll flag (0x01 = scroll active, 0x00 = static)
    mode_byte = 0x00 if scroll else 0x03
    scroll_flag = 0x01 if scroll else 0x00

    # Build packet
    pkt = bytearray(MAGIC)

    # Length byte - for packets > 255 bytes this is just the low byte
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
    pkt.append(mode_byte)  # [22] MODE: 0x00=scroll, 0x03=static
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
    pkt.append(scroll_flag)# [33] SCROLL: 0x01=on, 0x00=off
    pkt.append(speed)      # [34] speed
    pkt.append(0x00)       # [35]

    # Pixel data (offset 36+)
    for page in pages:
        for row_val in page:
            pkt.extend(struct.pack('<I', row_val & 0xFFFFFFFF))

    assert len(pkt) == total_packet_size, \
        f"Packet size mismatch: got {len(pkt)}, expected {total_packet_size}"
    
    return bytes(pkt)
