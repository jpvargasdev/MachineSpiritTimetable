#!/usr/bin/env python3
"""Parse btsnoop HCI log and extract BLE ATT Write commands."""

import struct
import sys

def parse_btsnoop(filename):
    with open(filename, 'rb') as f:
        # Read header
        magic = f.read(8)
        if magic != b'btsnoop\x00':
            print(f"Not a btsnoop file! Magic: {magic}")
            return
        
        version, datalink_type = struct.unpack('>II', f.read(8))
        print(f"btsnoop version: {version}, datalink type: {datalink_type}")
        # datalink_type: 1001 = HCI UART (H4), 1002 = HCI BSCP, 2001 = HCI Serial (H4)
        
        pkt_num = 0
        writes = []
        notifications = []
        
        while True:
            # Read packet header (24 bytes)
            hdr = f.read(24)
            if len(hdr) < 24:
                break
            
            orig_len, incl_len, flags, drops, ts = struct.unpack('>IIIII', hdr[:20])
            # Actually btsnoop uses: original length (4), included length (4), packet flags (4), cumulative drops (4), timestamp (8)
            orig_len, incl_len, flags, drops = struct.unpack('>IIII', hdr[:16])
            ts = struct.unpack('>q', hdr[16:24])[0]
            
            # Read packet data
            data = f.read(incl_len)
            if len(data) < incl_len:
                break
            
            pkt_num += 1
            
            # flags: bit 0 = direction (0=sent, 1=received), bit 1 = command/event
            direction = "SENT" if (flags & 1) == 0 else "RECV"
            is_cmd = (flags & 2) != 0
            
            if len(data) < 1:
                continue
            
            # H4 packet type
            h4_type = data[0]
            
            # We care about ACL data packets (type 0x02) which contain ATT
            if h4_type == 0x02 and len(data) > 5:
                # HCI ACL header: handle(2) + length(2)
                handle_flags = struct.unpack('<H', data[1:3])[0]
                acl_handle = handle_flags & 0x0FFF
                acl_len = struct.unpack('<H', data[3:5])[0]
                
                # L2CAP header: length(2) + CID(2)
                if len(data) > 9:
                    l2cap_len = struct.unpack('<H', data[5:7])[0]
                    l2cap_cid = struct.unpack('<H', data[7:9])[0]
                    
                    # CID 0x0004 = ATT
                    if l2cap_cid == 0x0004 and len(data) > 9:
                        att_opcode = data[9]
                        att_data = data[10:]
                        
                        # ATT Write Request (0x12) or Write Command (0x52)
                        if att_opcode in (0x12, 0x52) and len(att_data) >= 2:
                            att_handle = struct.unpack('<H', att_data[0:2])[0]
                            att_value = att_data[2:]
                            op_name = "WriteReq" if att_opcode == 0x12 else "WriteCmd"
                            hex_value = att_value.hex()
                            writes.append({
                                'pkt': pkt_num,
                                'dir': direction,
                                'op': op_name,
                                'handle': att_handle,
                                'value': hex_value,
                                'raw': att_value,
                                'len': len(att_value),
                            })
                        
                        # ATT Handle Value Notification (0x1B)
                        elif att_opcode == 0x1B and len(att_data) >= 2:
                            att_handle = struct.unpack('<H', att_data[0:2])[0]
                            att_value = att_data[2:]
                            notifications.append({
                                'pkt': pkt_num,
                                'dir': direction,
                                'handle': att_handle,
                                'value': att_value.hex(),
                                'len': len(att_value),
                            })
                        
                        # ATT Handle Value Indication (0x1D)
                        elif att_opcode == 0x1D and len(att_data) >= 2:
                            att_handle = struct.unpack('<H', att_data[0:2])[0]
                            att_value = att_data[2:]
                            notifications.append({
                                'pkt': pkt_num,
                                'dir': direction,
                                'op': 'Indication',
                                'handle': att_handle,
                                'value': att_value.hex(),
                                'len': len(att_value),
                            })
                        
                        # ATT Read Response (0x0B)
                        elif att_opcode == 0x0B:
                            att_value = att_data
                            # print(f"  #{pkt_num} {direction} ReadResp: {att_value.hex()}")
                        
                        # Print all ATT operations for debugging
                        ATT_OPCODES = {
                            0x01: "ErrorResp", 0x02: "ExchMTUReq", 0x03: "ExchMTUResp",
                            0x04: "FindInfoReq", 0x05: "FindInfoResp",
                            0x08: "ReadByTypeReq", 0x09: "ReadByTypeResp",
                            0x0A: "ReadReq", 0x0B: "ReadResp",
                            0x10: "ReadByGrpTypeReq", 0x11: "ReadByGrpTypeResp",
                            0x12: "WriteReq", 0x13: "WriteResp",
                            0x16: "PrepWriteReq", 0x17: "PrepWriteResp",
                            0x18: "ExecWriteReq", 0x19: "ExecWriteResp",
                            0x1B: "Notification", 0x1D: "Indication",
                            0x52: "WriteCmd",
                        }
        
        print(f"\nTotal packets: {pkt_num}")
        print(f"\n{'='*80}")
        print(f"ATT WRITE OPERATIONS ({len(writes)} found)")
        print(f"{'='*80}")
        for w in writes:
            print(f"  #{w['pkt']:4d} {w['dir']:4s} {w['op']:10s} handle=0x{w['handle']:04x} ({w['handle']:3d})  len={w['len']:3d}  data={w['value']}")
        
        print(f"\n{'='*80}")
        print(f"NOTIFICATIONS/INDICATIONS ({len(notifications)} found)")
        print(f"{'='*80}")
        for n in notifications:
            op = n.get('op', 'Notification')
            print(f"  #{n['pkt']:4d} {n['dir']:4s} {op:12s} handle=0x{n['handle']:04x} ({n['handle']:3d})  len={n['len']:3d}  data={n['value']}")
        
        # Group writes by handle
        print(f"\n{'='*80}")
        print("WRITES GROUPED BY HANDLE")
        print(f"{'='*80}")
        handles = sorted(set(w['handle'] for w in writes))
        for h in handles:
            hw = [w for w in writes if w['handle'] == h]
            print(f"\n  Handle 0x{h:04x} ({h}): {len(hw)} writes")
            for w in hw:
                print(f"    #{w['pkt']:4d} len={w['len']:3d}  {w['value']}")


if __name__ == '__main__':
    filename = sys.argv[1] if len(sys.argv) > 1 else '/Users/juan/LED/btsnoop_hci.log'
    parse_btsnoop(filename)
