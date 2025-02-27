import asyncio
from bleak import BleakScanner

async def scan_devices():
    while True:
        devices = await BleakScanner.discover()
        for device in devices:
            if "BT Croco" in device.name:
                print(f"Device: {device.name}, RSSI: {device.rssi}")
        await asyncio.sleep(2)  # Проверять каждые 2 секунды

asyncio.run(scan_devices())