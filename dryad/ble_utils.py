"""
    Name: ble_utils.py
    Author: Francis T
    Description:
        Source code for generic BLE functionality
"""
from bluepy.btle import Scanner, Peripheral, BTLEException
#from dryad.cache_node import NCLAS_UNKNOWN, NCLAS_BLUNO, NCLAS_PARROT
import logging
from time import sleep, time

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
CONN_ATTEMPT_INTERVAL = 1.5
CONN_ATTEMPT_TIMEOUT    = 35.0

TBL_SVC_ID = [
    { 'uuid' : UUID_BLUNO, 'device_type' : NTYPE_BLUNO },
    { 'uuid' : UUID_PARROT, 'device_type' : NTYPE_PARROT },
]

module_logger = logging.getLogger("main.ble_utils")

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

    # Establish a connection to the peripheral
    ppap = connect(address)
    if ppap == None:
        module_logger.error("Could not connect to device")
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

def discover_node_category(node_addr, node_id):
    node_class  = NCLAS_UNKNOWN
    node_type   = NTYPE_UNKNOWN

    # Check the device type
    node_type = check_device_type(node_addr, node_id)

    if ( not node_type == NTYPE_UNKNOWN ):
        # If the device type is either BLUNO or PARROT_FP, then
        #   classify it as a SENSOR device
        if ( node_type == NTYPE_BLUNO ) or ( node_type == NTYPE_PARROT ):
            node_class = NCLAS_SENSOR

        elif node_type == NTYPE_UNUSED:
            node_class = NCLAS_UNUSED


    return (node_type, node_class)

def connect(address):
    module_logger.info("[{}] Attempting to connect".format(address))

    peripheral = None
    retries = 0
    is_connected = False
    start_time = time()

    while (peripheral is None) and (retries < MAX_CONN_RETRIES):
        conn_success = True
        conn_attempt_time = time()

        try:
            peripheral = Peripheral(address, "public")
        except Exception as e:
            module_logger.error("[{}] Connecton failed: {}".format(address, e.message))
            conn_success = False

        elapsed_time = time() - conn_attempt_time

        # End the loop if connection is successful
        if conn_success:
            module_logger.debug("[{}] Overall connect time: {} secs, Total retries: {}".format(address, time() - start_time, retries))
            is_connected = True
            break

        # Put out a warning and cut down retries if our connect attempt exceeds thresholds
        if elapsed_time > CONN_ATTEMPT_TIMEOUT:
            module_logger.debug("[{}] Connect attempt took {} secs".format(address, elapsed_time))
            module_logger.warning("[{}] Connect attempt exceeds threshold. Is the device nearby?".format(address))
            break

        retries += 1

        sleep(CONN_ATTEMPT_INTERVAL)
        module_logger.debug("[{}] Attempting to connect ({})...".format(address, retries))

    # Check if a successful connection was established
    if (is_connected):
        module_logger.info("[{}] Connected.".format(address))

        return peripheral

    # Otherwise, indicate that a connection problem has occurred
    module_logger.error("[{}] Failed to connect to device".format(address))

    return None


