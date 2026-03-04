package display

import (
	"fmt"

	"xyaod/internal/bitmap"
	"xyaod/internal/ble"
	"xyaod/internal/protocol"
)

// Screen is the high-level interface for the XyaoLED display.
type Screen struct {
	client *ble.Client
}

// NewScreen creates a Screen. Pass empty string to use the default device name.
func NewScreen(name string) *Screen {
	return &Screen{client: ble.NewClient(name)}
}

// Connect connects to the LED display.
func (s *Screen) Connect() error {
	return s.client.Connect()
}

// Disconnect disconnects from the LED display.
func (s *Screen) Disconnect() error {
	return s.client.Disconnect()
}

// IsConnected returns whether the screen is connected.
func (s *Screen) IsConnected() bool {
	return s.client.IsConnected()
}

// Render sends text to the LED display.
// If preview is true it returns ASCII art and does not send to the device.
func (s *Screen) Render(text, color string, scroll bool, speed, brightness uint8, scale int, preview bool) (string, error) {
	rgb := bitmap.ParseColor(color)
	pages := bitmap.RenderTextToPages(text, scale)

	if preview {
		return bitmap.PagesToASCII(pages), nil
	}

	return "", s.send(pages, rgb, scroll, speed, brightness)
}

// RenderTwoLines sends two lines of text to the LED display.
// If preview is true it returns ASCII art without sending.
func (s *Screen) RenderTwoLines(line1, line2, color string, scroll bool, speed, brightness uint8, useMedium, preview bool) (string, error) {
	rgb := bitmap.ParseColor(color)
	pages := bitmap.RenderTwoLines(line1, line2, useMedium)

	if preview {
		return bitmap.PagesToASCII(pages), nil
	}

	return "", s.send(pages, rgb, scroll, speed, brightness)
}

func (s *Screen) send(pages [][]uint32, color [3]uint8, scroll bool, speed, brightness uint8) error {
	handshake := protocol.BuildHandshake()
	textInit := protocol.BuildTextInit(0x03, 0x02)
	bmp, err := protocol.BuildBitmap(pages, color, 0x03, 0x02, brightness, speed, scroll)
	if err != nil {
		return fmt.Errorf("build bitmap: %w", err)
	}

	if _, err := s.client.Write(handshake); err != nil {
		return fmt.Errorf("write handshake: %w", err)
	}
	if _, err := s.client.Write(textInit); err != nil {
		return fmt.Errorf("write text_init: %w", err)
	}
	if _, err := s.client.Write(bmp); err != nil {
		return fmt.Errorf("write bitmap: %w", err)
	}

	return nil
}
