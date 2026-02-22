#!/usr/bin/env python3
"""Analyze the XyaoLED protocol from captured HCI snoop data."""

# All captured writes to handle 0x0082 (characteristic AE01 on service AE00)
# All start with: 99 aa 00 2e ff 88
#
# Notifications from handle 0x0084 (characteristic AE02 on service AE00) 
# All start with: 88 ff

writes = [
    # Pkt 336: First command after connection (session 1)
    "99aa002eff881f0000000d001a02140a14100501000997abdff87300000000",
    # Pkt 346: Second command (session 1)
    "99aa002eff88120011000e01010100000000",
    # Pkt 453: First command after reconnection (session 2)
    "99aa002eff881f0000000f001a02140a14270501005d212dfbed8100000000",
    # Pkt 458: 
    "99aa002eff880e00010710000200",
    # Pkt 461:
    "99aa002eff880e00010311000200",
    # Pkt 463:
    "99aa002eff880f000a001200000000",
    # Pkt 465:
    "99aa002eff881100060013020000000000",
    # Pkt 469:
    "99aa002eff880e00010514000200",
    # Pkt 520:
    "99aa002eff880e00010b15000200",
    # Pkt 523:
    "99aa002eff880e00010c16000200",
    # Pkt 663: First after reconnection (session 3)
    "99aa002eff88120011001702010100000000",
    # Pkt 666:
    "99aa002eff881f00000018001a02140a1519050100c57c822e071100000000",
    # Pkt 671:
    "99aa002eff88120011001902010100000000",
]

notifications = [
    "88ff000b010120001000040064050100501800020100009d",  # After pkt 336
    "88ff000b01012000100004016417010050180002010000b0",  # After pkt 453
    "88ff040100000000000b97",                              # After pkt 465
    "88ff000b010120001000040164020100501800020100009b",  # After pkt 663
    "88ff000b010120001000040064020100501800020100009a",  # After pkt 671
]

print("=" * 100)
print("PROTOCOL ANALYSIS")
print("=" * 100)

print("\n--- HEADER ANALYSIS ---")
print("All write commands start with: 99 aa 00 2e ff 88")
print("  99 aa     = Magic/sync bytes")
print("  00 2e     = Unknown (could be device address fragment '2E')")
print("  ff 88     = Unknown constant")
print("All notification responses start with: 88 ff")
print("  88 ff     = Response magic (note: reversed from ff 88)")

print("\n--- INDIVIDUAL PACKET ANALYSIS ---")
for i, w in enumerate(writes):
    b = bytes.fromhex(w)
    print(f"\n  Write #{i+1}: {w}")
    print(f"    Header:  {w[:12]}  (99aa002eff88)")
    payload = w[12:]
    print(f"    Payload: {payload}")
    print(f"    Payload bytes: {' '.join(payload[j:j+2] for j in range(0, len(payload), 2))}")
    
    # Byte 6 (first payload byte) seems to be the payload length
    payload_len_byte = b[6]
    print(f"    Byte[6] = 0x{payload_len_byte:02x} ({payload_len_byte}) -- total payload len = {len(b) - 6}")
    
    # Byte 7 seems to vary
    print(f"    Byte[7] = 0x{b[7]:02x} ({b[7]})")

print("\n\n--- GROUPING BY PAYLOAD LENGTH ---")
for length in sorted(set(len(bytes.fromhex(w)) for w in writes)):
    matching = [(i, w) for i, w in enumerate(writes) if len(bytes.fromhex(w)) == length]
    print(f"\n  Length {length} bytes ({len(matching)} commands):")
    for idx, w in matching:
        b = bytes.fromhex(w)
        print(f"    #{idx+1}: {w}")
        # After the 6-byte header, what do we have?
        payload = b[6:]
        print(f"         payload: {payload.hex()}")

print("\n\n--- BYTE-BY-BYTE COMPARISON (14-byte packets) ---")
fourteen_byte = [(i, w) for i, w in enumerate(writes) if len(bytes.fromhex(w)) == 14]
print(f"Found {len(fourteen_byte)} 14-byte packets:")
for idx, w in fourteen_byte:
    b = bytes.fromhex(w)
    parts = ' '.join(f'{x:02x}' for x in b)
    print(f"  #{idx+1}: {parts}")

print("\nByte positions for 14-byte packets:")
print("  Pos:  0  1  2  3  4  5 | 6  7  8  9 10 11 12 13")
print("  ----- header ----------|--- payload ------------")
for idx, w in fourteen_byte:
    b = bytes.fromhex(w)
    parts = ' '.join(f'{b[j]:02x}' for j in range(len(b)))
    print(f"  #{idx+1}: {parts}")

print("\n\n--- BYTE-BY-BYTE COMPARISON (18-byte packets) ---")
eighteen_byte = [(i, w) for i, w in enumerate(writes) if len(bytes.fromhex(w)) == 18]
for idx, w in eighteen_byte:
    b = bytes.fromhex(w)
    parts = ' '.join(f'{x:02x}' for x in b)
    print(f"  #{idx+1}: {parts}")

print("\n\n--- BYTE-BY-BYTE COMPARISON (31-byte packets) ---")
thirtyone_byte = [(i, w) for i, w in enumerate(writes) if len(bytes.fromhex(w)) == 31]
for idx, w in thirtyone_byte:
    b = bytes.fromhex(w)
    parts = ' '.join(f'{x:02x}' for x in b)
    print(f"  #{idx+1}: {parts}")

print("\n\n--- NOTIFICATION ANALYSIS ---")
for i, n in enumerate(notifications):
    b = bytes.fromhex(n)
    parts = ' '.join(f'{x:02x}' for x in b)
    print(f"  Notif #{i+1} (len={len(b)}): {parts}")

print("\n\n--- SEQUENCE NUMBER ANALYSIS ---")
print("Looking at bytes that increment across packets...")
for i, w in enumerate(writes):
    b = bytes.fromhex(w)
    # Bytes 8-9 might be a sequence number
    if len(b) > 11:
        print(f"  #{i+1}: b[8:10]={b[8]:02x} {b[9]:02x}  b[10:12]={b[10]:02x} {b[11]:02x}")

print("\n\n--- CHECKSUM ANALYSIS ---")
print("Checking if last byte(s) are a checksum...")
for i, w in enumerate(writes):
    b = bytes.fromhex(w)
    # Check XOR of all bytes
    xor_all = 0
    for x in b:
        xor_all ^= x
    # Check sum mod 256
    sum_all = sum(b) & 0xFF
    sum_no_last = sum(b[:-1]) & 0xFF
    xor_no_last = 0
    for x in b[:-1]:
        xor_no_last ^= x
    print(f"  #{i+1}: last_byte=0x{b[-1]:02x}  xor_all=0x{xor_all:02x}  sum_all=0x{sum_all:02x}  sum_no_last=0x{sum_no_last:02x}  xor_no_last=0x{xor_no_last:02x}")
