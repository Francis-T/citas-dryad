"""
    Name: main-mt.py
    Author: Francis T
    Desc: Multi-threaded version of the Dryad program
"""

import logging

from Queue import Queue
from dryad.database import DryadDatabase
from dryad_mt.link_listener import LinkListenerThread
from threading import Thread, Event, Timer

TRIG_EVENT_TIMEOUT = 120.0
CUSTOM_DATABASE_NAME = "dryad_test_cache.db"

""" Initialize the logger """
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

""" Initialize the Cache Node """
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

""" Main function """
def main():
    if init() == False:
        return False

    logger.info("Program started")

    # Create concurrency objects
    trig_event = Event()
    queue = Queue()

    # Create the threads
    listen_thread = LinkListenerThread(trig_event, queue)
    # listen_thread.daemon = True
    listen_thread.start()

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
    except KeyboardInterrupt:
        logger.info("Interrupted")

    # Cancel running threads
    listen_thread.cancel()
    listen_thread.join()

    logger.info("Program finished")

    return True


if __name__ == "__main__":
    main()


