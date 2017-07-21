#
#   Aggregator Node Network Class
#   Author: Francis T
#
#   Class for Aggregator Node Networking functionality
#
import os
import logging
import dryad.ble_utils as ble_utils
from dryad.database import DryadDatabase

ADTYPE_LOCAL_NAME = 9

SYS_CMD_BNAME = "hciconfig hci0 name | grep \"Name\" | sed -r \"s/\s+Name: '(.+)'/\\1/g\""
SYS_CMD_ADDR = "hciconfig hci0 name | grep \"BD Address\" | sed -r \"s/\s+BD Address: (.+)  ACL.+/\\1/g\"" 

class BaseAggregatorNodeNetwork():
    def __init__(self):
        self.logger = logging.getLogger("main.AggregatorNode.Network")
        self.node_list = []

        return

    def init_network_records(self):
        db = DryadDatabase()

        # Check if SELF record already exists
        records = db.get_nodes(node_class="SELF")
        if (records != False) and (len(records) > 0):
            db.close_session()
            return False


        # If it does not, then create a node record for it
        self_name = os.popen(SYS_CMD_BNAME).read().split(' ')[0].strip()
        result = db.insert_or_update_node( name       = self_name,
                                           node_class = "SELF",
                                           site_name  = "????",
                                           lat        = 14.37,
                                           lon        = 120.58 )
        if result == False:
            self.logger.error("Unable to create own node record")
            db.close_session()
            return False

        # Create a node device record for it as well
        self_address = os.popen(SYS_CMD_ADDR).read().strip()
        result = db.insert_or_update_device( address     = self_address,
                                             node_id     = self_name,
                                             device_type = "RPI" )
        if result == False:
            self.logger.error("Unable to create own device record")
            db.close_session()
            return False

        db.close_session()

        return True

    def reload_network_info(self):
        db = DryadDatabase()
        
        # Get all nodes
        node_records   = db.get_nodes()
        device_records = db.get_devices()

        if (node_records == False) or (device_records == False):
            db.close_session()
            return

        # Reload the running node list
        self.node_list = []
        for device in device_records:
            # Get the matching node in the node records list
            node_name = device.node_id
            node_addr = device.address
            node_type = device.device_type  # This will contain an Enum
            node_class = "UNKNOWN"          # This will contain an Enum
            for node in node_records:
                if node.name == device.node_id:
                    node_class = node.node_class

            # Add the node to the list
            self.node_list.append( { "id" : node_name,
                                     "addr" : node_addr,
                                     "type" : node_type.name, 
                                     "class" : node_class.name } )

        self.logger.debug( str(self.node_list) )

        db.close_session()

        return True

    def scan_le_nodes(self):
        self.logger.info("Scanning for devices...")
        try:
            scanned_devices = ble_utils.scan_for_devices(12)
        except Exception as e:
            self.logger.error("Scan Failed: " + str(e))
            return False

        self.logger.info("Scan finished.")

        scanned_str = "Scanned Devices: | "
        for device in scanned_devices:
            node_id = device.getValueText( ADTYPE_LOCAL_NAME )
            if node_id == None:
                continue

            scanned_str +=  node_id + " | "

        self.logger.debug(scanned_str)

        # Update the node device list stored in our database
        if self.update_scanned_devices(scanned_devices) == False:
           return False

        # Reload our node list from the database
        if self.reload_network_info() == False:
           return False

        return True

    def update_scanned_devices(self, scanned_devices):
        db = DryadDatabase()

        for device in scanned_devices:
            record_exists = False

            # Check if this node already exists in the database
            result = db.get_devices(address=device.addr.upper())
            if (result != False) or \
               ((type(result) == type(list)) and (len(result) > 0)):
                self.logger.debug(str(result))
                self.logger.info("Node already exists: [{}] {}/{}"
                                    .format( result.device_type,
                                             result.node_id,
                                             result.address ))
                continue

            # Get the name of the device first
            node_id = device.getValueText( ADTYPE_LOCAL_NAME )
            if node_id == None:
                self.logger.error("Could not obtain device name: {}"
                                    .format(device.addr))
                continue

            node_id = node_id.strip('\x00')

            # Add a node record in the database
            result = db.insert_or_update_node( name       = node_id,
                                               node_class = "UNKNOWN",
                                               site_name  = "????",
                                               lat        = 14.37,
                                               lon        = 120.58 )
            if result == False:
                self.logger.error("Unable to add node record")
                continue

            # Add a node device record in the database
            result = db.insert_or_update_device( address     = device.addr.upper(),
                                                 node_id     = node_id,
                                                 device_type = "UNKNOWN" )
            if result == False:
                self.logger.error("Unable to add node device record")
                continue

        db.close_session()

        return

    def get_node_list(self):
        return self.node_list


