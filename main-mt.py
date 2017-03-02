"""
    Name: main-mt.py
    Author: Jerelyn C / Francis T
    Desc: Source code for the multi-threaded version of the Dryad program
"""

import logging
import time
import sys

from queue import Queue
from threading import Thread, Event, Timer

from dryad.cache_node import CacheNode
from dryad.database import DryadDatabase
from dryad.request_handler import RequestHandler
from dryad.link_listener import LinkListenerThread
from dryad.node_state import NodeState

VERSION  = "1.0.3"
TRIG_EVENT_TIMEOUT = 120.0
SAMPLING_INTERVAL = 60.0 * 60.0
AUTO_SHUTDOWN_INTERVAL = 60.0 * 20.0
REFRESH_INTERVAL = 60.0 * 15.0

MAX_TRIAL_COUNT = 10
MAX_SAMPLE_COUNT = 100
SCANNING_INTERVAL = 600.0

DEBUG_MODE = False

CUSTOM_DATABASE_NAME = "dryad_test_cache.db"

# Exit codes
EXIT_NORMAL     = 0
EXIT_ERROR      = 1
EXIT_POWEROFF   = 2

class InputThread(Thread):
    def __init__(self, queue, hevent):
        Thread.__init__(self)
        self.queue = queue
        self.hevent = hevent
        self.is_running = False
        return

    def run(self):
        self.is_running = True
        while self.is_running:
            cmd = input("> ")
            if (cmd == "QUIT"):
                self.queue.put("SHUTDOWN")
                self.hevent.set()
                is_running = False
                break
            else:
                self.queue.put(cmd)
                self.hevent.set()

        return

    def cancel(self):
        self.is_running = False
        return

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

def add_shutdown_task():
    logger.info("Time limit reached. Performing shutdown...")
    queue.put("SHUTDOWN")
    trig_event.set()
    return

def add_refresh_task():
    logger.info("Time limit reached. Refreshing program...")
    queue.put("REFRESH")
    trig_event.set()
    return

# @desc     Main function
# @return   An integer exit code:
def main():
    exit_code = EXIT_NORMAL
    if init_logger() == False:
        exit_code = EXIT_ERROR
        return exit_code

    logger.info("Program started")

    # Create concurrency objects
    global trig_event
    global queue
    global state
    global SAMPLING_INTERVAL
    global AUTO_SHUTDOWN_INTERVAL

    trig_event = Event()
    queue = Queue()
    state = NodeState()

    cache_node = CacheNode(event=trig_event,
                           queue=queue,
                           db_name=CUSTOM_DATABASE_NAME)
    cache_node.initialize()

    # Set the initial state to INACTIVE
    state.set_state("INACTIVE")

    # Create the Request Handler object
    request_hdl = RequestHandler(trig_event, queue, state, CUSTOM_DATABASE_NAME, VERSION)

    # Create the Link Listener thread
    listen_thread = LinkListenerThread(request_hdl)
    listen_thread.daemon = True
    listen_thread.start()

    # Create the Sampling Timer thread
    sampling_timer = Timer(5.0, add_sampling_task)
    if cache_node.is_activated():
        sampling_timer.start()

    ## Create the Auto Shutdown Timer thread
    #auto_shutdown_timer = Timer(AUTO_SHUTDOWN_INTERVAL, add_shutdown_task)
    #auto_shutdown_timer.start()

    # Initialize timing variables
    last_scan_time = 0.0

    if DEBUG_MODE == True:
        # Enable debug input thread
        input_thread = InputThread(queue, trig_event)
        input_thread.start()

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
                cache_node.set_activated(True)
                if sampling_timer.is_alive() == False:
                    add_sampling_task()
                    state.set_state("IDLE")

            elif msg == "DEACTIVATE":
                cache_node.set_activated(False)
                if sampling_timer.is_alive() == True:
                    sampling_timer.cancel()
                state.set_state("INACTIVE")

            elif msg == "SET_PARAMS":
                cache_node.set_node_sample_max()
                cache_node.set_node_sampling_duration()
                SAMPLING_INTERVAL = cache_node.get_sampling_interval()
                
            elif msg == "SHUTDOWN":
                state.set_state("UNKNOWN")
                exit_code = EXIT_POWEROFF
                break

            elif msg == "SCAN":
                state.set_state("SCANNING")
                cache_node.scan_le_nodes()
                state.set_state("IDLE")

            elif msg == "SAMPLING_START":
                # Load basic sensor node info from the database
                if ( cache_node.reload_node_list() == False ):
                    logger.info("Reload sensor node list failed")

                # Collect data (blocking)
                state.set_state("GATHERING")
                cache_node.collect_data(queue)
                state.set_state("IDLE")

                # Queue up another sampling task
                # sampling_timer = Timer(SAMPLING_INTERVAL, add_sampling_task)
                # sampling_timer.start()
                #exit_code = EXIT_POWEROFF
                #break

            elif msg == "SAMPLING_END":
                state.set_state("IDLE")
                # TODO Our state machine is f---ed up for now
                Timer(REFRESH_INTERVAL, add_refresh_task).start()
           
            elif msg == "REFRESH":
                exit_code = EXIT_NORMAL
                break

    except KeyboardInterrupt:
        logger.info("Interrupted")
        exit_code = EXIT_ERROR

    # Cancel running threads
    cache_node.cancel_read()

    if sampling_timer.is_alive():
        sampling_timer.cancel()
        sampling_timer.join(20.0)

    if listen_thread.is_alive():
        listen_thread.cancel()
        listen_thread.join(20.0)

    if (DEBUG_MODE == True) and (input_thread.is_alive()):
        input_thread.cancel()
        input_thread.join(20.0)

    logger.info("Program finished")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())

