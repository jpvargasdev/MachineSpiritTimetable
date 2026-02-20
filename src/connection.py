"""BLE connection manager for XyaoLED devices."""

from bleak import BleakClient, BleakScanner


# GATT handles for service 0000AE00
# Write characteristic AE01 = handle 129
# Notify characteristic AE02 = handle 131
WRITE_HANDLE = 129
NOTIFY_HANDLE = 131


class Connection:
    def __init__(self, address: str):
        self.address = address
        self.client = BleakClient(address)
        self._notification_callbacks = []

    def on_notify(self, callback):
        """Register a callback for device notifications."""
        self._notification_callbacks.append(callback)

    def _handle_notification(self, sender, data: bytearray):
        for cb in self._notification_callbacks:
            cb(sender, data)

    async def connect(self):
        """Connect to the device and subscribe to notifications."""
        await self.client.connect()
        await self.client.start_notify(NOTIFY_HANDLE, self._handle_notification)
        return self.client.is_connected

    async def disconnect(self):
        """Unsubscribe and disconnect."""
        try:
            await self.client.stop_notify(NOTIFY_HANDLE)
        except Exception:
            pass
        await self.client.disconnect()

    async def write(self, data: bytes):
        """Write raw bytes to the device (write-without-response)."""
        await self.client.write_gatt_char(WRITE_HANDLE, data, response=False)

    @property
    def is_connected(self) -> bool:
        return self.client.is_connected

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, *args):
        await self.disconnect()


async def scan(name_filter: str = "XyaoLED", timeout: float = 5.0):
    """Scan for XyaoLED devices. Returns list of (address, name, rssi)."""
    devices = await BleakScanner.discover(timeout=timeout)
    results = []
    for d in devices:
        if d.name and name_filter.lower() in d.name.lower():
            results.append((d.address, d.name))
    return results
