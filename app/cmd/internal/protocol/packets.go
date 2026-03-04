package protocol

import (
	"encoding/binary"
	"encoding/hex"
	"fmt"
)

// magic is the 6-byte packet header.
var magic, _ = hex.DecodeString("99aa002eff88")

// BuildHandshake returns a captured handshake packet (replays work fine).
func BuildHandshake() []byte {
	b, _ := hex.DecodeString("99aa002eff881f00000001001a02140f1b02050100435897dc6dd500000000")
	return b
}

// BuildTextInit builds a text_init packet (cmd 0x04, 13 bytes).
func BuildTextInit(sub, seq byte) []byte {
	pkt := make([]byte, len(magic))
	copy(pkt, magic)
	pkt = append(pkt, 0x0D, 0x00, 0x04, sub, seq, 0xFF, 0x00)
	return pkt
}

// BuildBitmap builds a bitmap packet (cmd 0x07).
// pages: list of pages, each page = 16 uint32 row values.
// color: [3]uint8 {R, G, B}.
func BuildBitmap(pages [][]uint32, color [3]uint8, sub, seq byte, brightness, speed uint8, scroll bool) ([]byte, error) {
	numPages := len(pages)
	bitmapDataLen := 12 + numPages*64
	totalPacketSize := 36 + numPages*64

	r, g, b := color[0], color[1], color[2]

	modeByte := byte(0x03) // static
	scrollFlag := byte(0x00)
	if scroll {
		modeByte = 0x00
		scrollFlag = 0x01
	}

	pkt := make([]byte, 0, totalPacketSize)
	pkt = append(pkt, magic...)
	pkt = append(pkt, byte(totalPacketSize&0xFF)) // [6] length low byte
	pkt = append(pkt, 0x00)                       // [7]
	pkt = append(pkt, 0x07)                       // [8] CMD = bitmap
	pkt = append(pkt, sub)                        // [9]
	pkt = append(pkt, seq)                        // [10]

	// bitmap_data_len LE uint16
	var lenBuf [2]byte
	binary.LittleEndian.PutUint16(lenBuf[:], uint16(bitmapDataLen))
	pkt = append(pkt, lenBuf[:]...)

	pkt = append(pkt,
		0x00,           // [13]
		0x02,           // [14]
		0x00,           // [15]
		0x02,           // [16]
		0x01,           // [17]
		0x00,           // [18]
		0x00,           // [19]
		byte(numPages), // [20] page count
		0x00,           // [21]
		modeByte,       // [22] MODE
		0x00,           // [23]
		0x00,           // [24]
		0x00,           // [25]
		0x00,           // [26]
		r,              // [27]
		g,              // [28]
		b,              // [29]
		0x00,           // [30]
		0x00,           // [31]
		brightness,     // [32]
		scrollFlag,     // [33]
		speed,          // [34]
		0x00,           // [35]
	)

	// Pixel data
	var rowBuf [4]byte
	for _, page := range pages {
		for _, rowVal := range page {
			binary.LittleEndian.PutUint32(rowBuf[:], rowVal)
			pkt = append(pkt, rowBuf[:]...)
		}
	}

	if len(pkt) != totalPacketSize {
		return nil, fmt.Errorf("packet size mismatch: got %d, expected %d", len(pkt), totalPacketSize)
	}

	return pkt, nil
}
