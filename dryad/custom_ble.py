"""
    Name: custom_ble.py
    Author: Francis T
    Description:
        Source code for generic BLE functionality
"""
from bluepy.btle import Scanner, Peripheral, BTLEException
#from dryad.cache_node import NCLAS_UNKNOWN, NCLAS_BLUNO, NCLAS_PARROT
import logging
from time import sleep

UUID_BLUNO  = "0000dfb0-0000-1000-8000-00805f9b34fb"
UUID_PARROT = "39e1fa00-84a8-11e2-afba-0002a5d5c51b"

NCLAS_UNKNOWN   = "UNKNOWN"
NCLAS_UNUSED    = "UNUSED"
NCLAS_SENSOR    = "SENSOR"

NTYPE_UNKNOWN   = "UNKNOWN"
NTYPE_UNUSED    = "UNUSED"
NTYPE_BLUNO     = "BLUNO"
NTYPE_PARROT    = "PARROT"

MAX_CONN_RETRIES = 5

TBL_SVC_ID = [
    { 'uuid' : UUID_BLUNO, 'device_type' : NTYPE_BLUNO },
    { 'uuid' : UUID_PARROT, 'device_type' : NTYPE_PARROT },
]

module_logger = logging.getLogger("main.custom_ble")

# @desc     Scans for nearby BLE devices
# @return   A list of Bluepy ScanEntry objects
def scan_for_devices(num):
    scanner = Scanner()
    module_logger.info("Scanning for devices...")
    scanned_devices = scanner.scan(20.0)
    module_logger.info("Scan finished")
    return scanned_devices

# @desc     Performs checks to determine the type of Sensor Node this BLE device is
# @return   A String containing the device class
def check_device_type(address, name):
    device_type = NTYPE_UNKNOWN

    ppap = Peripheral(None, "public")

    module_logger.info("Attempting to connect to " + str(name) + "(" + address + ")...")
    # Attempt to connect a few times
    retries = 0
    is_connected = True
    while retries < 5:
        is_connected = True
        try:
            ppap.connect(address)
        except Exception as e:
            is_connected = False

        if is_connected:
            module_logger.info("Connected to {} ({})".format(address, name))
            break

        retries += 1

        # Sleep for a few seconds before retrying connection
        sleep(1.5 * retries)

        module_logger.info("Attempting to connect ({})...".format(retries))

    # Return if the device could not be connected to
    if not is_connected:
        module_logger.error("Could not connect to {} ({})".format(address, name))
        return device_type

    # Return the device type based on the BLE services on the device
    for ref_service in TBL_SVC_ID:
        try:
            service = ppap.getServiceByUUID(ref_service['uuid'])
        except BTLEException:
            module_logger.error("Service {} not found. ".format(ref_service['uuid']))
            continue
        
        if not service == None:
            ppap.disconnect()
            device_type = ref_service['device_type']

            module_logger.info("Service {} found. ".format(ref_service['uuid']))
            module_logger.info("Device type is {}. ".format(device_type))
            break

    # If the device did not satisfy any of the service-by-uuid checks, flag it as
    #   unusable
    if device_type == NTYPE_UNKNOWN:
        device_type = NTYPE_UNUSED

    return device_type

