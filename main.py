"""
    Name:   main.py
    Author: Francis T
    Description: 
        This is the prototype program for the Dryad relay node. This serves as 
         a bridge between sensor data on the Parrot Flower Power / Bluno pH
         and the Mobile App.

        Eventually, we will rewrite this code in C++ using Bluez directly
         in order to get a bit more control on the comms aspect (and maybe
         to get a little more speed and less memory consumption as well)
"""
import time
import string
import json
import sys
import logging

# import pprint

from dryad import custom_ble as ble
from dryad import parrot_ble
from dryad import bluno_ble
from dryad import mobile_bt
from dryad import database as ddb
import test

from threading import Event

MAX_SAMPLE_COUNT = 1000
MAX_TRIAL_COUNT = 10
USE_LED = True
USE_INTERACTIVE = False 

"""
    Performs data gathering from the BLE-based Sensor Nodes
"""
def gather_device_data(name, address):
    logger.info("Found Device: name={}, address={}".format(name, address))
    if name == "":
        return

    # Setup the device object based on the type of sensor node
    #   we're dealing with here
    device = None
    device_type = ble.check_device_type(address, name)
    if device_type == "BLUNO_BEETLE":
        device = bluno_ble.Bluno(address)
    elif device_type == "PARROT_FP":
        device = parrot_ble.Parrot(address)

    if device == None:
        logger.info("Device detected neither a bluno nor parrot flower.")
        return


    # Obtain the event handle
    handle_event = device.get_event_hdl()

    # Start the device
    if device.start() == False:
        print("Initialize failed")
        device.stop()
        return


    logger.info("Reading device name...")
    logger.info("Name:{0}".format(device.get_name()))

    if device_type == "PARROT_FP":
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
        print("Interrupted")

    if device_type == "PARROT_FP":
        if USE_LED:
            device.trigger_led(False)

    logger.info("Finishing up live measurements...")
    device.stop()

    print("Done.")

    return {"node_id" : name, "data" : device.get_data()}
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
    Handles connections from Mobile Nodes which will retrieve data from this
     particular Cache Node
"""
def handle_mobile_nodes(mobile_conn, db):
    """ Trigger indicator LEDs to show that RPi is ready to be connected to """
    # GPIO.output(16, GPIO.LOW)

    if mobile_conn.listen() == False:
        return False

    request = mobile_conn.receive_data()
    if request == None:
        return False
 
    """ Draw unsent data from our database """
    unsent_records = db.get_data()
    resp_data = []
    proc_ids = []
    for record in unsent_records:
        proc_ids.append( record[0] )
        resp_data.append( {
            "timestamp" : record[2],
            "source" : record[1],
            "data" : json.loads(record[3])
        })

    """ Send the data as a response """
    if mobile_conn.send_response(resp_data) == False:
        return False

    if mobile_conn.send_response("") == False:
        return False

    """ Once data is sent successfully, we can mark off the records whose
        IDs we took note of earlier in our database """
    for rec_id in proc_ids:
        db.set_data_uploaded(rec_id)
 
    if mobile_conn.disconnect() == False:
        return False

    """ Untrigger indicator LEDs to show that RPi is going back to data gathering mode """
    # GPIO.output(16, GPIO.HIGH)

    return True

def save_gathered_data(db, gathered_data):
    logger.info("Saving data to database...")
    count = 0
    for node_data in gathered_data:
        source_id   = node_data['node_id']
        data        = node_data['data']

        for sensor_data in data:
            ts = sensor_data['time']
#            read_data = { "type" : sensor_data["sensor"],
#                          "value" : sensor_data["reading"] }
            read_data = '{ "type" : "%s", "value" : %f }' % ( sensor_data["sensor"], sensor_data["reading"] )
            db.add_data(read_data, source=source_id, timestamp=ts)
            # print("Data added: %s, %s, %li" % (str(read_data), source_id, ts)

            if (count % 5) == 0:
                logger.info("Data saved:{0} records".format(count))
            count += 1

    return True

"""
    Main function
"""
def main():
    # logger creation
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
    
    logger.info("Program has started.")     

    is_running = True
    data_record = []
    # GPIO.setmode(GPIO.BCM)
    # GPIO.setup(16, GPIO.OUT)

    """ Initialize our database """
    db = ddb.DryadDatabase()
    if db.connect("dryad_test_cache.db") == False:
        return False

    if db.setup() == False:
        return False

    """ Initialize our Mobile Node link handler """
    mobile_link = mobile_bt.MobileNode()
    mobile_link.init_socket(300.0)

    while True:
        try:    
            # Phase I: Gather data from the sensor nodes **
            devices = find_sensor_nodes()

            if len(devices.items()) <= 0:
                break

            for address, name in devices.items():
                node_data = gather_device_data(name, address)
                if node_data:
                    data_record.append(node_data) 

            if len(data_record) > 0:
                # Phase II : Save gathered data to a database
                save_gathered_data(db, data_record)
                # pp = pprint.PrettyPrinter(indent=2)
                # pp.pprint(data_record)
                data_record = []

                # Phase III : Listen for incoming connections
                handle_mobile_nodes(mobile_link, db)

        except KeyboardInterrupt:
            logger.info("Operation cancelled")
            is_running = False
            break
        if not USE_INTERACTIVE:
            break
            

    """ Cleanup our Mobile Node link handler """
    mobile_link.destroy()

    """ Close our database """
    db.disconnect()

    if is_running:
        return True

    return False

## MAIN PROGRAM ##
if not USE_INTERACTIVE:
    if main() == False:
        sys.exit(1)
    else:
        sys.exit(0)

else:
    while True:
        if not main():
            print("---------------------------------------------")
            print("  Terminating program...Have a Nice Day! :)  ")
            print("---------------------------------------------")
            break

        print("----------------------------------")
        print("  Restarting after 10 seconds...  ")
        print("----------------------------------")
        time.sleep(10.0)

