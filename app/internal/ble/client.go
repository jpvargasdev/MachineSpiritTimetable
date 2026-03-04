package ble

import (
	"fmt"
	"time"

	"tinygo.org/x/bluetooth"
)

const (
	defaultName   = "XyaoLED_44BF"
	writeUUID     = "0000ae01-0000-1000-8000-00805f9b34fb"
	writeService  = "0000ae30-0000-1000-8000-00805f9b34fb"
	notifyUUID    = "0000ae02-0000-1000-8000-00805f9b34fb"
	notifyService = "0000ae00-0000-1000-8000-00805f9b34fb"
	notifyTimeout = 3 * time.Second
)

// Client is a BLE client for the XyaoLED device.
type Client struct {
	name      string
	adapter   *bluetooth.Adapter
	device    *bluetooth.Device
	writeChar bluetooth.DeviceCharacteristic
	notifyCh  chan []byte
	connected bool
}

// NewClient creates a new BLE client. Pass empty string to use the default device name.
func NewClient(name string) *Client {
	if name == "" {
		name = defaultName
	}
	return &Client{
		name:     name,
		adapter:  bluetooth.DefaultAdapter,
		notifyCh: make(chan []byte, 1),
	}
}

// Connect enables the BLE adapter, scans for the device by name and connects.
func (c *Client) Connect() error {
	if err := c.adapter.Enable(); err != nil {
		return fmt.Errorf("enable adapter: %w", err)
	}

	found := make(chan bluetooth.ScanResult, 1)
	err := c.adapter.Scan(func(adapter *bluetooth.Adapter, result bluetooth.ScanResult) {
		if result.AdvertisementPayload.LocalName() == c.name {
			found <- result
			adapter.StopScan()
		}
	})
	if err != nil {
		return fmt.Errorf("start scan: %w", err)
	}

	var foundDevice bluetooth.ScanResult
	select {
	case foundDevice = <-found:
	case <-time.After(15 * time.Second):
		return fmt.Errorf("device %q not found within 15s", c.name)
	}

	dev, err := c.adapter.Connect(foundDevice.Address, bluetooth.ConnectionParams{})
	if err != nil {
		return fmt.Errorf("connect: %w", err)
	}
	c.device = &dev

	time.Sleep(300 * time.Millisecond)

	services, err := dev.DiscoverServices(nil)
	if err != nil {
		return fmt.Errorf("discover services: %w", err)
	}

	for _, svc := range services {
		svcUUID := svc.UUID().String()
		chars, err := svc.DiscoverCharacteristics(nil)
		if err != nil {
			continue
		}
		for _, ch := range chars {
			uuid := ch.UUID().String()
			if uuid == writeUUID && svcUUID == writeService {
				c.writeChar = ch
			}
			if uuid == notifyUUID && svcUUID == notifyService {
				ch.EnableNotifications(func(buf []byte) {
					data := make([]byte, len(buf))
					copy(data, buf)
					select {
					case c.notifyCh <- data:
					default:
					}
				})
			}
		}
	}

	time.Sleep(200 * time.Millisecond)
	c.connected = true
	return nil
}

// Disconnect closes the BLE connection.
func (c *Client) Disconnect() error {
	c.connected = false
	if c.device != nil {
		return c.device.Disconnect()
	}
	return nil
}

// IsConnected returns whether the client is connected.
func (c *Client) IsConnected() bool {
	return c.connected
}

// Write sends data to the device and waits for a notification response.
// Returns nil response on timeout (non-fatal).
func (c *Client) Write(data []byte) ([]byte, error) {
	// Drain stale notification
	select {
	case <-c.notifyCh:
	default:
	}

	if _, err := c.writeChar.WriteWithoutResponse(data); err != nil {
		return nil, fmt.Errorf("write: %w", err)
	}

	select {
	case resp := <-c.notifyCh:
		return resp, nil
	case <-time.After(notifyTimeout):
		return nil, nil
	}
}
