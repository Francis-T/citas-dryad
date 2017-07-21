#
#   Collect Thread Class
#   Author: Francis T
#
#   Thread for handling data collection operations
#

import logging
import dryad.ble_utils as ble_utils

from random import randint
from time import sleep

from threading import Thread, Event, Lock
from queue import Queue

from dryad.database import DryadDatabase
from dryad.sensor_node.bluno_sensor_node import BlunoSensorNode
from dryad.sensor_node.parrot_sensor_node import ParrotSensorNode

MAX_QUEUE_TASKS = 4

class CollectThread(Thread):
    def __init__(self, parent):
        Thread.__init__(self)

        self.logger = logging.getLogger("main.AggregatorNode.CollectThread")
        self.parent = parent

        self.node_queue = None
        self.node_queue_size = MAX_QUEUE_TASKS

        self.worker_threads = None
        self.active_flag = False
        self.active_flag_lock = Lock()

        self.active_wait_events = []

        return

    def classify_node(self, node):
        db = DryadDatabase()

        self.logger.info("Discovering node classification...")
        try:
            node['type'], node['class'] = ble_utils.discover_node_category(node['addr'], node['id'])
        except Exception as e:
            self.logger.error("Failed to discover node classification: {}".format(e))
            db.close_session()
            return False

        # Update the database node information
        result = db.insert_or_update_node( name       = node['id'],
                                           node_class = node['class'] )
        if result == False:
            self.logger.error("Unable to update node record")
            db.close_session()
            return False

        # Update the node device record in the database
        result = db.insert_or_update_device( address     = node['addr'],
                                             node_id     = node['id'],
                                             device_type = node['type'] )
        if result == False:
            self.logger.error("Unable to update node device record")
            db.close_session()
            return False

        db.close_session()

        return True

    def instantiate_node(self, node_info, wait_event):
        if node_info['type'] == ble_utils.NTYPE_BLUNO:
            return BlunoSensorNode( node_info['id'],
                                    node_info['addr'],
                                    wait_event )

        elif node_info['type'] == ble_utils.NTYPE_PARROT:
            return ParrotSensorNode( node_info['id'],
                                     node_info['addr'],
                                     wait_event )

        # if the node cannot be instantiated due to its type
        #   being unknown, then simply return None
        return None

    def process_node(self):
        while self.check_active():
            node = self.node_queue.get()
            if (node == None):
                break

            self.logger.debug("Processing {}...".format(node['id']))
            
            # Check if the node id is valid
            if (node['id'] == None) or (node['id'] == ''):
                self.logger.info("Skipping blank \"node\" with address {}".format(node['addr']))
                self.node_queue.task_done()
                continue

            # Classify the node if it hasn't been classified yet
            if node['class'] == ble_utils.NCLAS_UNKNOWN:
                result = self.classify_node(node)
                if result == False:
                    self.node_queue.task_done()
                    continue

            # Based on the node type, instantiate a Node object and read
            wait_event = Event()
            node_instance = self.instantiate_node(node, wait_event)
            if node_instance == None:
                self.logger.error( "Could not instantiate node: {} ({})".format(
                                    node['id'], node['addr']) )

                self.node_queue.task_done()
                continue

            if node_instance.connect() == False:
                self.logger.error( "Could not connect to node: {} ({})".format(
                                    node['id'], node['addr']) )

                self.node_queue.task_done()
                continue

            if self.check_active() == False:
                self.node_queue.task_done()
                continue

            node_instance.start()

            self.active_wait_events.append( { 'id' : node['id'],
                                              'event' : wait_event } )

            wait_event.wait()

            node_instance.stop()

            self.node_queue.task_done()
            if node != None:
                self.logger.debug("Processed {}!".format(node['id']))

        return

    def offload_data(self):
        db = DryadDatabase()
        
        session_data = db.get_session_data()

        blk_count = 0
        curr_session = 0
        prev_session = 0
        data_block = {}
        for reading in session_data:
            # Save the current session id
            curr_session = reading.session_id

            # Extract the data type and value from the 'content' string
            data_type = reading.content.split(":")[0].strip()
            data_val  = reading.content.split(":")[1].strip()

            # If this particular data type has already been stored in this
            #  data block, then we should create a new block for it instead
            if data_type in data_block.keys():
                # Reset block counter when transitioning from one session to
                #   the next. This ideally should not happen since data offload
                #   happens immediately after collection anyway but this is a
                #   good precaution in case of unexpected crashes.
                if (curr_session != prev_session):
                    prev_session = curr_session
                    blk_count = 0

                # Increase the block count for this session
                blk_count += 1

                # Save the block to the database
                db.add_data( blk_id=blk_count,
                             session_id=reading.session_id,
                             source_id=reading.source_id,
                             content=str(data_block),
                             timestamp=reading.timestamp )

                # Create a new blank data block
                data_block = {}

            else:
                data_block[data_type] = data_val

        # If the last data block is non-empty, then offload its contents to the
        #   archive as well
        if len(data_block) > 0:
            if (curr_session != prev_session):
                prev_session = curr_session
                blk_count = 0

            # Increase the block count for this session
            blk_count += 1

            # Save the block to the database
            db.add_data( blk_id=blk_count,
                         session_id=reading.session_id,
                         source_id=reading.source_id,
                         content=str(data_block),
                         timestamp=reading.timestamp )

        db.clear_session_data()

        db.close_session()

        return

    def setup_worker_threads(self):
        self.worker_threads = []

        db = DryadDatabase()

        if db.get_current_session() != False:
            self.logger.error("A previous session is still active. Closing it...")
            db.terminate_session()

        db.start_session()
        db.close_session()

        for i in range(self.node_queue_size):
            t = Thread(target=self.process_node)
            t.start()
            self.worker_threads.append(t)

        return

    def cleanup_worker_threads(self):
        for i in range(self.node_queue_size):
            self.node_queue.put(None)

        for t in self.worker_threads:
            self.logger.debug("Cleaning up thread: {}".format(t.name))
            t.join()

        db = DryadDatabase()
        db.terminate_session()
        db.close_session()

        return

    def run(self):
        self.set_active(True)

        self.logger.debug("Data collection started")
        self.node_queue = Queue(self.node_queue_size)

        # Load node list from the Aggregator Node
        node_list = self.parent.get_node_list()
        if node_list == None:
            self.logger.error("Error could not reload node list!")
            return

        self.setup_worker_threads()

        # Add nodes to the queue
        for node in node_list:
            self.logger.debug("Added node to queue: {}".format(node['id']))
            self.node_queue.put(node)

        # Wait until all nodes enqueued have been processed
        self.node_queue.join()
        self.logger.debug("All nodes processed!")

        # Cleanup remaining threads
        self.cleanup_worker_threads()

        # Compress and offload collected data to data archive
        self.offload_data()

        self.logger.debug("Data collection finished")

        self.set_active(False)

        self.parent.add_task("STOP_COLLECT")

        return

    def cancel(self):
        self.logger.debug("Data collection cancelled")

        self.set_active(False)

        for event in self.active_wait_events:
            event['event'].set()
            self.active_wait_events.remove(event) # TODO Not sure if safe or...

        return

    def check_active(self):
        result = False

        self.active_flag_lock.acquire()
        result = self.active_flag
        self.active_flag_lock.release()

        return result

    def set_active(self, flag):
        self.active_flag_lock.acquire()
        self.active_flag = flag
        self.active_flag_lock.release()

        return

