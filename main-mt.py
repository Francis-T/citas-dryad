"""
    Name: main-mt.py
    Author: Francis T
    Desc: Source code for the multi-threaded version of the Dryad program
"""

import logging
import time

from Queue import Queue
from threading import Thread, Event, Timer

from dryad import custom_ble as ble
from dryad import parrot_ble
from dryad import bluno_ble

from dryad.database import DryadDatabase
from dryad_mt.request_handler import RequestHandler
from dryad_mt.link_listener import LinkListenerThread
from dryad_mt.node_state import NodeState

TRIG_EVENT_TIMEOUT = 120.0
SAMPLING_INTERVAL = 10.0
#SAMPLING_INTERVAL = 240.0
MAX_TRIAL_COUNT = 10
MAX_SAMPLE_COUNT = 100
SCANNING_INTERVAL = 600.0
CUSTOM_DATABASE_NAME = "dryad_test_cache.db"
USE_LED = True

""" 
    Initializes the logger
"""
def init_logger():
    global logger
    logger = logging.getLogger("main")
    logger.setLevel(logging.DEBUG)

    # console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.DEBUG)

    # file handler
    fh = logging.FileHandler("cache_node.log")

    # formatter
    formatter = logging.Formatter("%(asctime)s - [%(levelname)s] [%(threadName)s] (%(module)s:%(lineno)d) %(message)s") 
 
    # ch setting
    ch.setFormatter(formatter)
    logger.addHandler(ch)   

    # fh setting
    fh.setFormatter(formatter)
    logger.addHandler(fh) 

    return True

"""
    Initializes the Cache Node
"""
def init():
    # Initialize the logger
    if init_logger() == False:
        logger.error("Initialization Failed")
        return False

    # Setup the database
    ddb = DryadDatabase()
    if ddb.connect(CUSTOM_DATABASE_NAME) == False:
        logger.error("Initialization Failed")
        return False

    if ddb.setup() == False:
        logger.error("Initialization Failed")
        return False

    ddb.disconnect()

    logger.info("Initialization Finished")
    return True

def add_sampling_task():
    queue.put("SAMPLING_START")
    trig_event.set()
    return

"""
    Locates nearby BLE-based Sensor Nodes by conducting a BLE scan / discovery
"""
def find_sensor_nodes():
    devices = {};
    device_count = 0
    trial_count = MAX_TRIAL_COUNT
    while device_count < 1:
        logger.info("Looking for devices...")
        devices = ble.scan_for_devices(2)
        device_count = len(devices.items())
        logger.info("Found {} device/s".format(device_count))
        if device_count == 0:
            trial_count -= 1
            if trial_count < 0:
                logger.info("Could not find any nearby sensor nodes!")
                break
        time.sleep(1.5)
    return devices

"""
    Saves newly-discovered nodes into the database
"""
def save_new_sensor_nodes(node_list):
    ddb = DryadDatabase()
    if ddb.connect(CUSTOM_DATABASE_NAME) == False:
        logger.error("Load Sensor Node Info Failed")
        return False

    for address, name in node_list:
        # If this device already exists, then skip it
        if ddb.get_node_info(address):
            continue

        ddb.add_node_info(address, name, "UNKNOWN")

    ddb.disconnect()

    return True

"""
    Loads sensor node information from the database
"""
def load_sensor_nodes():
    ddb = DryadDatabase()
    if ddb.connect(CUSTOM_DATABASE_NAME) == False:
        logger.error("Load Sensor Node Info Failed")
        return False

    node_list = ddb.get_nodes('C_TYPE = "UNKNOWN" OR C_TYPE = "SENSOR"')

    ddb.disconnect()
    
    return node_list

"""
    Gathers sensor data
"""
def gather_sensor_data(address, name, ntype, nclass):
    # Skip unnamed devices
    if name == "":
        return

    # If the device type is UNKNOWN, then we have to know what kind
    #   of device we're dealing with and remember it for the future
    if ntype == "UNKNOWN":
        nclass = "UNKNOWN"
        device = None

        ddb = DryadDatabase()
        if ddb.connect(CUSTOM_DATABASE_NAME) == False:
            logger.error("Failed to update device info")
            return

        device_type = ble.check_device_type(address, name)
        if device_type == "BLUNO_BEETLE" or device_type == "PARROT_FP":
            nclass = device_type
            if ddb.update_node(address, node_type="SENSOR", node_class=device_type) == False:
                logger.error("Failed to update device info")

        ddb.disconnect()

 
    # Setup the device object based on the node class
    if nclass == "BLUNO_BEETLE":
        # Initialize our Bluno device
        device = bluno_ble.Bluno(address)

    elif nclass == "PARROT_FP":
        # Initialize our Parrot Flower Power device
        device = parrot_ble.Parrot(address)

    else:
        logger.error("Cannot initialize unknown device class")
        return
            
    # Obtain the event handle
    handle_event = device.get_event_hdl()

    # Start the device
    if device.start() == False:
        logger.error("Sensor Node Initialize failed")
        device.stop()
        return

    # Read the device name
    logger.info("Reading device name...")
    logger.info("Name:{0}".format(device.get_name()))

    if nclass == "PARROT_FP":
        if USE_LED:
            device.trigger_led(True)
            logger.info("Triggering Parrot flower LED")

    logger.info("Reading data...")
    counter = MAX_SAMPLE_COUNT
    try:
        stop_time = time.time() + 12.0
        while (counter > 0):
            handle_event.wait(2)
            counter -= 1
            if time.time() > (stop_time):
                logger.info("Time limit reached.")
                break
            handle_event.clear()
    except KeyboardInterrupt:
        logger.exception("Keyboard Interrupt detected")

    if nclass == "PARROT_FP":
        if USE_LED:
            device.trigger_led(False)

    logger.info("Finishing up live measurements...")
    device.stop()

    logger.info("Done.")

    return {"node_id" : name, "data" : device.get_data()}

"""
    Offloads gathered sensor data to the database for later access
"""
def offload_sensor_data(sensor_data):
    logger.info("Saving data to database...")
    count = 0

    # Connect to the database
    ddb = DryadDatabase()
    if ddb.connect(CUSTOM_DATABASE_NAME) == False:
        logger.error("Failed to update device info")
        return False

    for node_data in sensor_data:
        source_id   = node_data['node_id']
        data        = node_data['data']

        for sensor_data in data:
            ts = sensor_data['time']
            read_data = '{ "type" : "%s", "value" : %f }' % ( sensor_data["sensor"], sensor_data["reading"] )
            ddb.add_data(read_data, source=source_id, timestamp=ts)

            if (count % 5) == 0:
                logger.info("Data saved:{0} records".format(count))

            count += 1

    # Disconnect from the database
    ddb.disconnect()

    return True

"""
    Main function
"""
def main():
    if init() == False:
        return False

    logger.info("Program started")

    # Create concurrency objects
    global trig_event
    global queue
    global state

    trig_event = Event()
    queue = Queue()
    state = NodeState()

    # Set the initial state to INACTIVE
    state.set_state("INACTIVE")

    # Create the Request Handler object
    request_hdl = RequestHandler(trig_event, queue, state, CUSTOM_DATABASE_NAME)

    # Create the Link Listener thread
    listen_thread = LinkListenerThread(request_hdl)
    listen_thread.daemon = True
    listen_thread.start()

    # Create the Sampling Timer thread, but do not start it yet
    sampling_timer = Timer(SAMPLING_INTERVAL, add_sampling_task)
    sampling_timer.start()

    # Initialize timing variables
    last_scan_time = 0.0

    try:
        while True:
            # Wait for a trigger event
            logger.debug("Waiting for events...")
            trig_event.wait(TRIG_EVENT_TIMEOUT)
            trig_event.clear()

            # If nothing was added to the 
            if queue.empty():
                logger.debug("Timed out.")
                continue

            msg = queue.get()
            logger.info("Message received: {}".format(msg))

            if msg == "ACTIVATE":
                if sampling_timer.is_alive() == False:
                    sampling_timer = Timer(SAMPLING_INTERVAL, add_sampling_task)
                    sampling_timer.start()
                    state.set_state("IDLE")

            elif msg == "DEACTIVATE":
                if sampling_timer.is_alive() == True:
                    sampling_timer.cancel()
                state.set_state("INACTIVE")

            elif msg == "SHUTDOWN":
                state.set_state("UNKNOWN")
                break

            elif msg == "SAMPLING_START":
                # If there has been some time since our last scan,
                #   then perform one to find any new senor nodes
                if time.time() > (last_scan_time + SCANNING_INTERVAL):
                    state.set_state("SCANNING")
                    found_devices = find_sensor_nodes()
                    save_new_sensor_nodes(found_devices.items())

                # Load basic sensor node info from the database
                node_list = load_sensor_nodes()

                # Gather data from the known sensor nodes
                data_record = []
                for node in node_list:
                    node_data = gather_sensor_data(str(node[0]), str(node[1]), str(node[2]), str(node[3]))
                    if node_data:
                        data_record.append(node_data)
                
                # Save gathered data to the database if there are any
                if len(data_record) > 0:
                    offload_sensor_data(data_record)

                # Recreate the sampling timer again
                sampling_timer = Timer(SAMPLING_INTERVAL, add_sampling_task)
                sampling_timer.start()
                

    except KeyboardInterrupt:
        logger.info("Interrupted")

    # Cancel running threads
    listen_thread.cancel()
    listen_thread.join()

    logger.info("Program finished")

    return True


if __name__ == "__main__":
    main()


