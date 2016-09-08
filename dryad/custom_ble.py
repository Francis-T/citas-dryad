"""
    Name: custom_ble.py
    Author: Francis T
    Description:
        Source code for generic BLE functionality
"""
from bluetooth.ble import DiscoveryService, GATTRequester, GATTResponse
import logging

UUID_BLUNO  = "0000dfb0-0000-1000-8000-00805f9b34fb"
UUID_PARROT = "39e1fa00-84a8-11e2-afba-0002a5d5c51b"

"""
    Scans for nearby BLE devices
"""
def scan_for_devices(num):
    service = DiscoveryService()
    return service.discover(num)

"""
    Performs checks to determine the type of Sensor Node this BLE device is
"""

module_logger = logging.getLogger("main.custom_ble")

def check_device_type(address, name):
    device_type = "UNKNOWN"
    resp = GATTResponse()
    req = GATTRequester(address, False)


    module_logger.info("Attempting to connect to" + name + "(" + address + ")...")
    req.connect(True)

    primaries = req.discover_primary()
#    try:
#        req.discover_primary_async(response)
#        if not response.wait(15):
#            print("Discover primary services failed: Timed out")
#            req.disconnect()
#            return device_type
#        primaries = resp.received()
#
#    except:
#        print("Discover primary services failed")
#        return "UNKNOWN"

    for pri_svc_id in primaries:
        if pri_svc_id['uuid'] == UUID_BLUNO:
            device_type = "BLUNO_BEETLE"

        if pri_svc_id['uuid'] == UUID_PARROT:
            device_type = "PARROT_FP"

    req.disconnect()
    return device_type


