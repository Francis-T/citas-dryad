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
# import pprint

from dryad import custom_ble as ble
from dryad import parrot_ble
from dryad import mobile_bt
from dryad import database as ddb

from threading import Event

MAX_SAMPLE_COUNT = 1000
MAX_TRIAL_COUNT = 10
USE_LED = True
USE_INTERACTIVE = False 

"""
    Performs data gathering from the BLE-based Sensor Nodes
"""
def gather_device_data(name, address):
    print("Found Device: name={}, address={}".format(name, address))
    if name == "":
        return

    device = parrot_ble.Parrot(address)

    """ Obtain the event handle """
    handle_event = device.get_event_hdl()

    """ Start the device """
    if device.start() == False:
        print "Initialize failed"
        device.stop()
        return

    print "Reading device name..."
    print "Name:", device.get_name()

    if USE_LED:
        device.trigger_led(True)

    print("Reading data...")
    counter = MAX_SAMPLE_COUNT
    try:
        stop_time = time.time() + 60.0 ## TODO DEBUG
        while (counter > 0):
            handle_event.wait(2000)
            counter -= 1
            if time.time() > (stop_time):
                print("Time limit reached.")
                break
            handle_event.clear()
    except KeyboardInterrupt:
        print "Interrupted"

    if USE_LED:
        device.trigger_led(False)

    print "Finishing up live measurements..."
    device.stop()

    print "Done."

    return {"node_id" : name, "data" : device.get_data()}
    
"""
    Locates nearby BLE-based Sensor Nodes by conducting a BLE scan / discovery
"""
def find_sensor_nodes():
    devices = {};
    device_count = 0
    trial_count = MAX_TRIAL_COUNT
    while device_count < 1:
        print "Looking for devices..."
        devices = ble.scan_for_devices(2)
        device_count = len(devices.items())
        print("Found {} devices".format(device_count))
        if device_count == 0:
            trial_count -= 1
            if trial_count < 0:
                print("Could not find any nearby sensor nodes!")
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
    print "Saving data to database..."
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
            # print "Data added: %s, %s, %li" % (str(read_data), source_id, ts)

            if (count % 5) == 0:
                print "Data saved:", count," records"
            count += 1

    return True

"""
    Main function
"""
def main():
    is_running = True
    data_record = []

    """ setup GPIO control for LED """
    # GPIO.setmode(GPIO.BCM)
    # GPIO.setup(16, GPIO.OUT)

    """ Initialize our database """
    db = ddb.DryadDatabase()
    if db.connect("dryad_test_cache.db") == False:
        return

    if db.setup() == False:
        return

    """ Initialize our Mobile Node link handler """
    mobile_link = mobile_bt.MobileNode()
    mobile_link.init_socket(300.0)

    while True:
        try:
            # Phase I : Gather data from the sensor nodes ##
            devices = find_sensor_nodes()

            if len(devices.items()) <= 0:
                break

            for address, name in devices.items():
                node_data = gather_device_data(name, address)
                if node_data:
                    data_record.append(node_data) 

            if len(data_record) > 0:
                # Phase II : Save gathered data to a database
                # save_gathered_data(db, data_record)   ## TODO DEBUG
                # pp = pprint.PrettyPrinter(indent=2)
                # pp.pprint(data_record)
                data_record = []

                # Phase III : Listen for incoming connections
                handle_mobile_nodes(mobile_link, db)

        except KeyboardInterrupt:
            print("Operation cancelled")
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
    main()
else:
    while True:
        if not main():
            print "---------------------------------------------"
            print "  Terminating program...Have a Nice Day! :)  "
            print "---------------------------------------------"
            break

        print "----------------------------------"
        print "  Restarting after 10 seconds...  "
        print "----------------------------------"
        time.sleep(10.0)

