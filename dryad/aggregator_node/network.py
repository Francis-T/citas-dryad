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
        self_address = os.popen(SYS_CMD_ADDR).read().strip()
        result = db.insert_or_update_node( name       = self_name,
                                           address    = self_address,
                                           node_class = "SELF",
                                           site_name  = "????",
                                           lat        = 14.37,
                                           lon        = 120.58 )
        if result == False:
            self.logger.error("Unable to create own node record")
            db.close_session()
            return False

        db.close_session()

        return True

    def reload_network_info(self):
        db = DryadDatabase()
        
        # Get all nodes
        node_records = db.get_nodes()

        if node_records == False:
            db.close_session()
            return

        # Reload the running node list
        self.node_list = []
        for node in node_records:
            # Get the matching node in the node records list
            node_name = node.name
            node_address = node.address
            node_class = node.node_class

            # Add the node to the list
            self.node_list.append( { "id" : node_name,
                                     "addr" : node_address, 
                                     "class" : node_class } )

        self.logger.debug( str(self.node_list) )

        db.close_session()

        return True

    def get_node_list(self):
        return self.node_list
