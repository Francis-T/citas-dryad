
"""
    Name: cache_node.py
    Author: Francis T
    Desc: Source code for the Python object representation of Cache Node
"""
import logging
import dryad.custom_ble as ble
import os

from json import dumps
from bluepy.btle import Scanner
from threading import Thread, Event
from time import sleep, time
from dryad.database import DryadDatabase
from dryad.bluno_ble import Bluno
from dryad.parrot_ble import Parrot

IDX_NODE_ADDR   = 0
IDX_NODE_NAME   = 1
IDX_NODE_TYPE   = 2
IDX_NODE_CLASS  = 3

NTYPE_UNKNOWN   = "UNKNOWN"
NTYPE_UNUSED    = "UNUSED"
NTYPE_SENSOR    = "SENSOR"

ADTYPE_LOCAL_NAME = 9

SYS_CMD_BNAME = "hciconfig hci0 name | grep \"Name\" | sed -r \"s/\s+Name: '(.+)'/\\1/g\""
SYS_CMD_ADDR = "hciconfig hci0 name | grep \"BD Address\" | sed -r \"s/\s+BD Address: (.+)  ACL.+/\\1/g\"" 

CLASS = "CACHE"
TYPE = "SELF"

class ReadCompletionWaitTask(Thread):
    def __init__(self, cnode, read_threads):
        Thread.__init__(self)
        self.cnode = cnode
        self.read_threads = read_threads
        self.logger = logging.getLogger("main.cache_node.ReadCompletionWaitTask")
        return

    def run(self):
        self.logger.debug("Waiting for threads to finish...") 
        for t in self.read_threads:
            self.logger.debug("Waiting for thread to finish: " + str(t.name)) 
            t.join(60.0)
            self.logger.debug("Thread finished: " + str(t.name)) 

        self.logger.debug("All threads finished")
        self.cnode.notify_read_completion()

        return

    def cancel(self):
        self.logger.debug("Cancelling running threads...")
        for rt in self.read_threads:
            # Skip already-dead threads
            if rt.is_alive() == False:
                continue

            # Send a cancel request to this thread
            rt.cancel()
            self.logger.debug("Thread cancelled: " + str(t.name)) 

        return

class ReadNodeTask(Thread):
    def __init__(self, node_addr, node_name, node_type, node_class, db_name="dryad_test_cache.db"):
        Thread.__init__(self)
        self.logger = logging.getLogger("main.cache_node.ReadNodeTask")
        self.node_addr = node_addr
        self.node_name = node_name
        self.node_type = node_type
        self.node_class = node_class
        self.node_readings = None
        self.node_errors = None
        self.node_instance = None
        self.node_read_event = None
        self.db_name = db_name

        return

    ## --------------------- ##
    ## SEC01: Main Functions ##
    ## --------------------- ##
    def run(self):
        # Create the read completion notif event
        self.node_read_event = Event()
        
        # Instantiate this node
        self.node_instance = self.instantiate_node( self.node_addr,
                                                    self.node_name, 
                                                    self.node_type, 
                                                    self.node_class, 
                                                    self.node_read_event )
        if self.node_instance == None:
            self.logger.error("Failed to instantiate node")
            return False

        # Start collecting data from this node
        self.node_readings = self.collect_node_data(self.node_instance, self.node_read_event)

        # Operate on each sensor node reading returned by the sensor
        for reading in self.node_readings:
            read_time = 0
            data = {}

            # Parse the contents of this sensor node reading
            for key, val in reading.items():
                # Save the timestamp value to a separate variable
                if key == 'ts':
                    read_time = val
                    continue

                # Save the other values into a dict with the appropriate key
                #   e.g. data['key'] = "pH", data['val'] = 7.0
                data[key] = val

            # Add the origin part of the data
            # TODO Lat and Lon are still hardcoded
            data['origin'] = { "name" : self.node_name, 
                               "lat" : 14.37,                               "lon" : 120.58,
                               "lon" : 120.58,
                               "addr" : self.node_addr }

            # Add data to the local data cache
            #   Note: We might need _data_ to be a JSON-fmted string,
            #         so we use json.dumps() on data[]
            self.add_data(content=dumps(data), 
                          source=self.node_name, 
                          timestamp=read_time)

        return

    def cancel(self):
        if self.node_instance == None:
            return
        
        self.node_instance.stop()

        return

    ## --------------------- ##
    ## SEC02: Misc Functions ##
    ## --------------------- ##
    def instantiate_node(self, address, name, n_type, n_class, event):
        if n_class == ble.NCLAS_BLUNO:
            return Bluno(address, name, event)

        elif n_class == ble.NCLAS_PARROT:
            return Parrot(address, name, event)

        return None

    # @desc     Collect node data from the individual sensing nodes
    # @return   A Numpy array containing the readings
    def collect_node_data(self, node, event):
        # Start a read operation on the sensor node
        node.set_read_sample_size(10)
        node.start(time_limit=time() + 65.0)

        event.wait(240.0)
        event.clear()

        node.stop()
        
        return node.get_readings()

    # @desc     Adds new sensor data to the local data cache
    # @return   A boolean indicating success or failure
    def add_data(self, content, source, timestamp):
        ddb = DryadDatabase()
        if ddb.connect(self.db_name) == False:
            self.logger.error("Failed to connect to database")
            return False

        session_id = ddb.get_current_session()

        if ddb.add_data(session_id, source, content, "ATENEO") == False:
            self.logger.error("Failed to add new data")
            return False

        ddb.disconnect()
        return True

    # @desc     Retrieves the recently collected readings from this node
    # @return   A Numpy array of sensor readings
    def get_readings(self):
        return self.node_readings

class CacheNode():

    def __init__(self, db_name="dryad_test_cache.db"):
        self.node_list = []
        self.logger = logging.getLogger("main.cache_node.CacheNode")
        self.db_name = db_name
        self.read_completion_task = None

        return

    ## ----------------------- ##
    ## SECO1: Public Functions ##
    ## ----------------------- ##

    # @desc     Initializes the Cache Node
    # @return   A boolean indicating success or failure
    def initialize(self):
        self.setup_database()
        self.reload_node_list()
        self.logger.info("Initialization Finished")
        return True

    # @desc     Scans for nearby BLE node devices
    # @return   A boolean indicating success or failure
    def scan_le_nodes(self):
        scanner = Scanner()

        self.logger.info("Scanning for devices...")
        try:
            scanned_devices = scanner.scan(12.0)
        except Exception as e:
            self.logger.error("Scan Failed: " + str(e))
            return False

        self.logger.info("Scan finished.")

        scanned_str = "Scanned Devices: | "
        for device in scanned_devices:
            node_name = device.getValueText( ADTYPE_LOCAL_NAME )
            if node_name == None:
                continue

            scanned_str +=  node_name + " | "

        self.logger.debug(scanned_str)

        # Update the node list stored in our database
        if self.update_node_list(scanned_devices) == False:
            return False

        # Reload our node list from the database
        if self.reload_node_list() == False:
            return False

        return True

    # @desc     Collects data from nearby sensors
    # @params   queue - a non-null Queue object where completion tasks will be added
    # @return   A boolean indicating success or failure
    def collect_data(self, queue):
        if not self.read_completion_task == None:
            self.logger.error("Cannot start another collection task while another is still active")
            return            

        tasks = []
        for node in self.node_list:
            node_addr = node[ IDX_NODE_ADDR ]
            node_name = node[ IDX_NODE_NAME ]
            node_type = node[ IDX_NODE_TYPE ]
            node_class = node[ IDX_NODE_CLASS ]

            if (node_name == None) or (node_name == ''):
                self.logger.info("Skipping blank named {}".format(node_addr))
                continue

            # If we do not know the class and type of this node, then attempt
            #   to discover it by connecting to the device
            if node_type == NTYPE_UNKNOWN:
                node_class = ble.check_device_class( node_addr, node_name )
                if ( not node_class == ble.NCLAS_UNKNOWN ):
                    if ( node_class == ble.NCLAS_BLUNO ) or ( node_class == ble.NCLAS_PARROT ):
                        node_type = NTYPE_SENSOR

                    elif node_class == ble.NCLAS_UNUSED:
                        node_type = NTYPE_UNUSED

                    self.update_node_type( node_addr, node_type, node_class )
            
            # Create and start a new ReadNode task
            t = ReadNodeTask(node_addr, node_name, node_type, node_class)
            t.start()

            tasks.append(t)

            sleep(1.0)
        
        # Set up and start the read completion monitoring task
        self.read_completion_task = ReadCompletionWaitTask(self, tasks)
        self.read_completion_task.start()
        
        self.start_session()

        return

    # @desc     Retrieves the list of LE nodes known by the Cache Node
    # @return   A list of LE nodes
    def get_le_node_list(self):
        return self.node_list

    # @desc     Cancels ongoing sensor read tasks
    # @return   None
    def cancel_read(self):
        if (not self.read_completion_task == None):
            self.logger.debug("Thread cancel requested")
            self.read_completion_task.cancel()
            self.read_completion_task.join(60.0)
            self.notify_read_completion()
            return

        self.logger.debug("No threads to cancel")
        return

    # @desc     Notifies the cache node of read completion
    # @return   None
    def notify_read_completion(self):
        self.read_completion_task = None
        self.end_session()
        return

    ## -------------------------------------- ##
    ## SEC03: Database Manipulation Functions ##
    ## -------------------------------------- ##

    def start_session(self):
        ddb = DryadDatabase()
        if ddb.connect(self.db_name) == False:
            self.logger.error("Failed to connect to database")
            return False

        if ddb.start_capture_session() == False:
            self.logger.error("Failed to start capture session")
            return False

        ddb.disconnect()

    def end_session(self):
        ddb = DryadDatabase()
        if ddb.connect(self.db_name) == False:
            self.logger.error("Failed to connect to database")
            return False

        if ddb.end_capture_session() == False:
            self.logger.error("Failed to end capture session")
            return False

        ddb.disconnect()
        return True
        return True

    # @desc     Sets up the database
    # @return   A boolean indicating success or failure
    def setup_database(self):
        ddb = DryadDatabase()
        if ddb.connect(self.db_name) == False:
            self.logger.error("Failed to connect to database")
            return False

        # Setup the database if necessary
        if ddb.setup() == False:
            self.logger.error("Failed to setup database")
            return False
        
        self_name = os.popen(SYS_CMD_BNAME).read().split(' ')[0]
        self_address = os.popen(SYS_CMD_ADDR).read().strip()

        ddb.add_node(node_name=self_name, node_class=CLASS)
        ddb.add_node_device(node_addr=self_address, node_name = self_name, node_type = TYPE)

        ddb.disconnect()
        return True

    # @desc     Update node type info in the database
    # @return   A boolean indicating success or failure
    def update_node_type(self, addr, ntype, nclass=None):
        ddb = DryadDatabase()
        if ddb.connect(self.db_name) == False:
            self.logger.error("Failed to connect to database")
            return False

        # Setup the database if necessary
        if ddb.update_node_device(node_name=addr, node_type=ntype) == False:
            self.logger.error("Failed to update node type in database")
            return False

        if ddb.update_node(node_name=addr, node_class=nclass) == False:
            self.logger.error("Failed to update node type in database")
            return False

        ddb.disconnect()
        return True

    # @desc     Reloads the node list from the database
    # @return   A boolean indicating success or failure
    def reload_node_list(self):        
        ddb = DryadDatabase()
        if ddb.connect(self.db_name) == False:
            self.logger.error("Reload node list failed: Could not connect to database")
            return False

        # Reload our old node list
        self.node_list = ddb.get_nodes('C_TYPE = "UNKNOWN" OR C_TYPE = "SENSOR"')

        ddb.disconnect()
        return True

    # @desc     Updates the node list stored in the database
    # @return   A boolean indicating success or failure
    def update_node_list(self, node_list):
        ddb = DryadDatabase()
        if ddb.connect(self.db_name) == False:
            logger.error("Update node list failed: Could not connect to database")
            return False

        for node in node_list:
            # If this device already exists, then skip it
            if ddb.get_node_device(node.addr):
                continue

            node_name = node.getValueText( ADTYPE_LOCAL_NAME )
            if not node_name == None:
                ddb.add_node(node_name, "UNKNOWN")
                ddb.add_node_device(node.addr, node_name, "UNKNOWN")

        ddb.disconnect()

        return True


