"""
    Name: main-mt.py
    Author: Francis T
    Desc: Source code for the multi-threaded version of the Dryad program
"""

import logging
import time
import sys

from queue import Queue
from threading import Thread, Event, Timer

from dryad import custom_ble as ble
# from dryad import parrot_ble
from dryad import bluno_ble

from dryad.cache_node import CacheNode
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
USE_LED = True

CUSTOM_DATABASE_NAME = "dryad_test_cache.db"

# @desc     Initializes the logger
# @return   A boolean indicating success or failure
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

def add_sampling_task():
    queue.put("SAMPLING_START")
    trig_event.set()
    return

"""
    Main function
"""
def main():
    exit_code = 0
    if init_logger() == False:
        exit_code = -1
        return exit_code

    logger.info("Program started")

    # Create concurrency objects
    global trig_event
    global queue
    global state

    trig_event = Event()
    queue = Queue()
    state = NodeState()

    # Instantiate and initialize a CacheNode object
    cache_node = CacheNode()
    cache_node.initialize()

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
    #sampling_timer.start()

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
                exit_code = 1
                break

            elif msg == "SAMPLING_START":
                # If there has been some time since our last scan,
                #   then perform one to find any new senor nodes
                if time.time() > (last_scan_time + SCANNING_INTERVAL):
                    state.set_state("SCANNING")
                    cache_node.scan_le_nodes()

                # Load basic sensor node info from the database
                if ( cache_node.reload_node_list() == False ):
                    logger.info("Reload sensor node list failed")

                node_list = cache_node.get_le_node_list()
                print("Node List: " + str(node_list))

                # Collect data (blocking)
                cache_node.collect_data(queue)

                # cache_node.reload_node_list()
                # node_list = cache_node.get_le_node_list()
                # print("Node List: " + str(node_list))

                # # Gather data from the known sensor nodes
                # data_record = []
                # for node in node_list:
                #     node_data = gather_sensor_data(str(node[0]), str(node[1]), str(node[2]), str(node[3]))
                #     if node_data:
                #         data_record.append(node_data)
                # 
                # # Save gathered data to the database if there are any
                # if len(data_record) > 0:
                #     offload_sensor_data(data_record)

                # Recreate the sampling timer again
                sampling_timer = Timer(SAMPLING_INTERVAL, add_sampling_task)
                sampling_timer.start()
                

    except KeyboardInterrupt:
        logger.info("Interrupted")
        exit_code = -1

    # Cancel running threads
    listen_thread.cancel()
    listen_thread.join()

    logger.info("Program finished")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())


