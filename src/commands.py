"""XyaoLED protocol command builder.

Packet format:
  [99 aa 00 2e ff 88] [LEN] [00] [CMD_TYPE] [??] [SEQ] [DATA...]

  Header:    99 aa 00 2e ff 88  (6 bytes, constant)
  Byte 6:    Total packet length
  Byte 7:    0x00
  Byte 8:    Command type
  Byte 9:    Sub-type or flags
  Byte 10:   Sequence counter (increments per command)
  Byte 11+:  Command-specific data

Command types:
  0x11 = Power/mode control (ON=0x01, OFF/activate=0x02)
  0x0a = Clear/prepare display
  0x04 = Init data transfer
  0x07 = Bitmap/image data
"""

# Protocol constants
HEADER = bytes.fromhex("99aa002eff88")

# Display is 16 pixels tall, variable width
DISPLAY_HEIGHT = 16


def on_cmd(seq: int) -> bytes:
    """Turn the device ON (static mode)."""
    return HEADER + bytes([0x12, 0x00, 0x11, 0x00, seq & 0xFF, 0x01, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00])


def off_cmd(seq: int) -> bytes:
    """Turn the device OFF."""
    return HEADER + bytes([0x12, 0x00, 0x11, 0x00, seq & 0xFF, 0x02, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00])


def clear_cmd(seq: int) -> bytes:
    """Clear/prepare display for new content. Cmd type 0x0a."""
    return HEADER + bytes([0x0f, 0x00, 0x0a, 0x00, seq & 0xFF, 0x00, 0x00, 0x00, 0x00])


def text_init_cmd(seq: int) -> bytes:
    """Initialize text data transfer. Cmd type 0x04."""
    return HEADER + bytes([0x0d, 0x00, 0x04, 0x02, seq & 0xFF, 0xff, 0x00])


def text_data_cmd(seq: int, bitmap_rows: list[int], fg_color: tuple = (255, 0, 0),
                  bg_color: tuple = (0, 0, 0), speed: int = 60,
                  mode: int = 2, direction: int = 2) -> bytes:
    """Build the bitmap data packet for scrolling text.

    Packet layout (confirmed from HCI capture of "HI" in red):
      bytes 0-5:   header (99 aa 00 2e ff 88)
      byte 6:      total packet length
      byte 7:      0x00
      byte 8:      cmd type = 0x07
      byte 9:      sub type = 0x02
      byte 10:     sequence counter
      byte 11:     data_len = len(colors) + len(bitmap) = 12 + 64 = 76
      bytes 12-22: metadata (11 bytes)
      bytes 23-34: colors (12 bytes)
      bytes 35-98: bitmap (64 bytes = 16 rows x 4 bytes big-endian)
      byte 99:     padding 0x00

    Args:
        seq: Sequence number
        bitmap_rows: List of 32-bit integers, one per row (up to 16 rows).
                     MSB = leftmost pixel column.
        fg_color: (R, G, B) foreground color tuple
        bg_color: (R, G, B) background color tuple
        speed: Scroll speed (0x3c = 60 default)
        mode: Display mode (2 = scroll, 1 = static)
        direction: Scroll direction (2 = left)
    """
    # Metadata (11 bytes): controls scroll direction, font, speed, etc.
    meta = bytes([
        0x00,                          # padding
        0x00,                          # item index
        mode & 0xFF,                   # mode (2 = scroll)
        0x00,                          # padding
        direction & 0xFF,              # direction (2 = left)
        0x01,                          # font/size
        0x00, 0x00,                    # padding
        0x01,                          # bold flag
        0x00,                          # padding
        0x03,                          # speed setting
    ])

    # Colors (12 bytes): BG(4) + FG(4) + extra(4)
    colors = bytes([
        bg_color[0], bg_color[1], bg_color[2], 0x00,
        fg_color[0], fg_color[1], fg_color[2], 0x00,
        0x00, fg_color[0], 0x00, speed & 0xFF,
    ])

    # Bitmap: 4 bytes per row (big-endian 32-bit), padded to 16 rows
    padded_rows = (bitmap_rows + [0] * DISPLAY_HEIGHT)[:DISPLAY_HEIGHT]
    bitmap = b''
    for row_val in padded_rows:
        bitmap += (row_val & 0xFFFFFFFF).to_bytes(4, 'big')

    # data_len = colors + bitmap (does NOT include metadata)
    data_len = len(colors) + len(bitmap)

    # Build full packet
    # After header: total_len(1) + 0x00(1) + cmd(1) + sub(1) + seq(1) + data_len(1)
    #               + meta(11) + colors(12) + bitmap(64) + padding(1) = 94
    total_len = 6 + 1 + 1 + 1 + 1 + 1 + 1 + len(meta) + len(colors) + len(bitmap) + 1
    payload = bytes([
        total_len, 0x00, 0x07, 0x02, seq & 0xFF,
        data_len,
    ]) + meta + colors + bitmap + b'\x00'

    return HEADER + payload


def activate_cmd(seq: int) -> bytes:
    """Activate display after sending content (text/animation mode)."""
    return HEADER + bytes([0x12, 0x00, 0x11, 0x00, seq & 0xFF, 0x02, 0x01, 0x01, 0x00, 0x00, 0x00, 0x00])
