"""
    Name: custom_ble.py
    Author: Francis T
    Description:
        Source code for generic BLE functionality
"""
from bluetooth.ble import DiscoveryService

def scan_for_devices(num):
    service = DiscoveryService()
    return service.discover(num)

