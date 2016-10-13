
"""
    Name: cache_node.py
    Author: Francis T
    Desc: Source code for the Python object representation of Cache Node
"""
import logging
import dryad.custom_ble as ble

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

class ReadNodeTask(Thread):
    def __init__(self, node_addr, node_name, node_type, node_class):
        Thread.__init__(self)
        self.node_addr = node_addr
        self.node_name = node_name
        self.node_type = node_type
        self.node_class = node_class
        self.node_readings = None
        self.node_errors = None

        return

    ## --------------------- ##
    ## SEC01: Main Functions ##
    ## --------------------- ##
    def run(self):
        # Create the read completion notif event
        read_event = Event()
        
        # Instantiate this node
        node_inst = self.instantiate_node( self.node_addr,
                                           self.node_name, 
                                           self.node_type, 
                                           self.node_class, 
                                           read_event )

        if node_inst == None:
            node.logger.error("Failed to instantiate node")
            return False

        # Start collecting data from this node
        self.node_readings = self.collect_node_data(node_inst, read_event)

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

    # @desc     Retrieves the recently collected readings from this node
    # @return   A Numpy array of sensor readings
    def get_readings(self):
        return self.node_readings

class CacheNode():

    def __init__(self, db_name="dryad_test_cache.db"):
        self.node_list = []
        self.logger = logging.getLogger("main.cache_node.CacheNode")
        self.db_name = db_name

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
        
        # Wait until all read tasks have been completed
        for t in tasks:
            t.join(240.0)
            self.logger.debug("{} completed".format(t.name))

            print("READINGS>> " + str(t.get_readings()))

        self.logger.debug("Data Collection Finished")

        return

    # @desc     Retrieves the list of LE nodes known by the Cache Node
    # @return   A list of LE nodes
    def get_le_node_list(self):
        return self.node_list

    ## -------------------------------------- ##
    ## SEC03: Database Manipulation Functions ##
    ## -------------------------------------- ##

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
        if ddb.update_node(addr, node_type=ntype, node_class=nclass) == False:
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
            if ddb.get_node_info(node.addr):
                continue

            node_name = node.getValueText( ADTYPE_LOCAL_NAME )
            if not node_name == None:
                ddb.add_node_info(node.addr, node_name, "UNKNOWN")

        ddb.disconnect()

        return True



