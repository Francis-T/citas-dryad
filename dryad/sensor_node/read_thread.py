#
#   Read Thread Base Class
#   Author: Francis T
#
#   Base class for handling read operations from BLE Sensor Nodes
#

import logging

from time import time, sleep, ctime
from threading import Thread

from dryad.database import DryadDatabase

class ReadThread(Thread): #, metaclass=ABCMeta):
    def __init__(self, parent, func_read, readings, logger=None, event_done=None, event_read=None, \
                 event_error=None, read_samples=0, read_time=0, read_interval=0):
        Thread.__init__(self)

        self.parent = parent

        if logger == None:
            self.logger = logging.getLogger("main.read_thread")
        else:
            self.logger = logger

        self.perform_read = func_read

        self.readings = readings    # Where our readings will go

        self.event_done = event_done
        self.event_read = event_read
        self.event_error = event_error

        self.read_samples = read_samples
        self.read_time = read_time
        self.read_interval = read_interval

        self.readings_left = self.read_samples

        return

    def run(self):
        if self.parent == None:
            self.logger.error("No parent device".format())
            self.notify_error()
            self.notify_done()
            return False
        
        # Attempt to connect the parent device if it has not been connected yet
        if self.parent.is_connected == False:
            res = self.parent.connect()
            if (res == False):
                self.logger.error("[{}] Cannot read from unconnected device".format(self.parent.get_name()))
                self.notify_error()
                self.notify_done()
                return False

        # Setup the 'connection'
        self.parent.setup_connection()

        try:
            self.read_time = time() + self.read_time

            while self.should_continue_read():
                # Execute the read function defined by the parent node
                reading = self.perform_read(on_error_flag=self.event_error, on_read_flag=self.event_read)
                
                if (reading == None):
                    break

                # Temporarily store the read data somewhere
                self.cache_reading( reading )

                self.readings_left -= 1

                # Notify read event
                self.notify_read()

                # Sleep for a while in-between read events
                sleep(self.read_interval)

        except Exception as e:
            self.logger.exception("[{}] Exception occurred: {}".format(self.parent.get_name(), str(e)))
            self.notify_error()

        self.logger.info("[{}] Finished reading".format(self.parent.get_name()))

        # Notify event completion
        self.notify_done()
        
        self.logger.info("[{}] Stopping device".format(self.parent.get_name())) 
        self.parent.stop()

        return True

    def notify_error(self):
        if (self.event_error!= None):
            self.event_error.set()

        return

    def notify_read(self):
        if (self.event_read != None):
            self.event_read.set()

        return

    def notify_done(self):
        if (self.event_done != None):
            self.event_done.set()

        return

    def cache_reading(self, reading):
        self.readings.append( reading )

        # Store the timestamp parameter
        ts = reading['ts']

        # Store all other values
        db = DryadDatabase()
        for key in reading:
            if key == 'ts':
                continue

            result = db.add_session_data( self.parent.get_name(),
                                  str("{}: {}".format(key, reading[key])),
                                  ts )
            if result == False:
                print("Failed to add data")

        db.close_session()

        return

    def should_continue_read(self):
        self.logger.debug("Read Status: {}, {}, {}".format(self.parent.is_connected, ctime(self.read_time), self.readings_left))
        # If we're no longer connected, then stop reading
        if self.parent.is_connected == False:
            return False

        # If the current time exceeds our read until value,
        #   then return False immediately to stop reading
        if (self.read_time > 0) and (time() > self.read_time):
            self.logger.debug("[{}] Read time limit exceeded".format(self.parent.get_name()))
            self.logger.debug("    {} sec".format(str(self.read_time)))
            return False
            
        # Otherwise, check if the limit of readings has been
        #   reached and return False to stop reading
        if self.readings_left <= 0:
            self.logger.debug("[{}] Read sample limit exceeded".format(self.parent.get_name()))
            return False

        # Allow reading to continue otherwise
        return True

    def get_readings(self):
        return self.readings



