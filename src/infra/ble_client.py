"""BLE client for XyaoLED device using Bleak."""

import asyncio
from bleak import BleakClient


# Device constants
DEFAULT_ADDRESS = "84B8D1EA-C675-2DAA-8C2C-0D5D0A96D0A8"
WRITE_HANDLE = 129
NOTIFY_HANDLE = 131


class BLEClient:
    """Async BLE client for XyaoLED device."""
    
    def __init__(self, address: str = DEFAULT_ADDRESS):
        self.address = address
        self._client: BleakClient | None = None
        self._last_notify: bytes | None = None
        self._notify_event = asyncio.Event()
    
    def _notification_handler(self, sender, data: bytearray):
        """Handle incoming notifications from device."""
        self._last_notify = bytes(data)
        self._notify_event.set()
    
    async def connect(self) -> bool:
        """Connect to the BLE device."""
        self._client = BleakClient(self.address)
        connected = await self._client.connect()
        if connected:
            await self._client.start_notify(NOTIFY_HANDLE, self._notification_handler)
            await asyncio.sleep(0.3)
            return True
        return False
    
    async def disconnect(self):
        """Disconnect from the BLE device."""
        if self._client and self._client.is_connected:
            await self._client.stop_notify(NOTIFY_HANDLE)
            await self._client.disconnect()
        self._client = None
    
    @property
    def is_connected(self) -> bool:
        """Check if connected to device."""
        return self._client is not None and self._client.is_connected
    
    @property
    def mtu_size(self) -> int:
        """Get MTU size."""
        return self._client.mtu_size if self._client else 0
    
    async def write(self, data: bytes) -> bytes | None:
        """Write data to device and wait for notification response.
        
        Args:
            data: Bytes to send
            
        Returns:
            Notification response bytes, or None if timeout
        """
        if not self._client:
            raise RuntimeError("Not connected")
        
        self._notify_event.clear()
        self._last_notify = None
        
        await self._client.write_gatt_char(WRITE_HANDLE, data, response=False)
        
        try:
            await asyncio.wait_for(self._notify_event.wait(), timeout=3.0)
        except asyncio.TimeoutError:
            return None
        
        return self._last_notify
    
    async def __aenter__(self):
        await self.connect()
        return self
    
    async def __aexit__(self, *args):
        await self.disconnect()
