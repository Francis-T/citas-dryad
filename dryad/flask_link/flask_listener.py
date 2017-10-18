"""
    Name: flask_listener.py
    Author: Francis T
    Desc: Source code for FlaskListenerThread to be used by the multithreaded 
          version of the Dryad Cache Node program
"""
import logging
import time

from queue import Queue
from threading import Thread, Event

from dryad.flask_link.flask_link import FlaskLink

class FlaskListenerThread(Thread):

    """ Initialization function """
    def __init__(self, request_handler):
        self.SOCKET_TIMEOUT  = 5.0
        self.IDLE_TIMEOUT    = 120.0
        self.RECEIVE_TIMEOUT = self.SOCKET_TIMEOUT * 5.0
        self.MAX_RECEIVE_LEN = 2048
        self.MSG_TERMS = [ '\n', '\r', ';', '\0' ]
        self.MSG_SEP = ','

        self.request_hdl = request_handler
        self.link = None
        self.is_running = False
        self.logger = logging.getLogger("main.dryad.FlaskListenerThread")
        Thread.__init__(self)
        return

    """ Flags the running thread for cancellation """
    def cancel(self):
        self.logger.info("Thread cancelled")
        self.is_running = False
        return

    """ Sets up a link to the Mobile Node """
    def setup_link(self):
        self.link = FlaskLink()
        if self.link.init_socket(self.SOCKET_TIMEOUT) == False:
            self.logger.error("Failed to initialize socket")
            return False

        return True

    """ Destroys an existing link """
    def destroy_link(self):
        if self.link == None:
            return True

        self.link.destroy()
        return True

    """ Attempts to receive data from the remote device """
    def receive_data(self):
        if self.link.is_connected() == False:
            self.logger.error("Not connected")
            return False

        data_buf = ""

        recv_end_time = time.time() + self.RECEIVE_TIMEOUT

        # Keep trying to receive data until we've reached the projected receive
        #   timeout time OR this thread is no longer running
        while (time.time() < recv_end_time) and (self.is_running):
            data_part = self.link.receive_data()

            if (data_part is not None) or (data_part != None):
                try:
                    data_part = data_part.decode("utf-8")
                except:
                    self.logger.error("Data not in utf-8 format")
                    break

            # If the data part contains nothing, then try to receive data
            #   again if the thread is still running
            if (data_part is None) or (data_part == None):
                self.logger.info("No data received")
                self.link.connected = False
                break
   
            # if data_part == None:
            #     self.logger.info("No data received")
            #     if self.link.is_connected() == False:
            #         break

            #     continue

            # Add this data part to our data buffer
            data_buf += data_part

            # Also, extend our receive end time by a small bit for every
            #   successful piece of data received
            recv_end_time += 1.0

            # If this data part contains the terminator, then we can return
            #   the data_buffer's contents to the calling context
            for terminator in self.MSG_TERMS:
                if terminator in data_part:
                    return data_buf

            # If we've reached the maximum length of received data, then return
            #   the current data buffer contents to the calling context
            if len(data_buf) >= self.MAX_RECEIVE_LEN:
                return data_buf

        self.logger.info("Receive timed out. Returning received content...")
        return data_buf

    """ Run function for this thread """
    def run(self):
        if self.setup_link() == False:
            self.logger.error("Link setup failed")
            return
    
        self.is_running = True
        while self.is_running:
            # Listen for connections until one has been found; Otherwise, 
            #   simply return to the beginning of the loop
            if self.link.listen() == False:
                continue

            # Start a receive session
            self.logger.info("Session started.")
            session_end_time = time.time() + self.IDLE_TIMEOUT
            while (time.time() < session_end_time) and (self.is_running):
                msg = self.receive_data()

                if msg == "":
                    if self.link.is_connected() == False:
                        self.logger.info("Connection lost")
                        break
                    continue

                # Process the message
                self.request_hdl.handle_request(self.link, msg)

                if self.link.is_connected() == False:
                    self.logger.info("Connection lost")
                    break

                # Update the session end time
                session_end_time = time.time() + self.IDLE_TIMEOUT


            # Indicate if this session has idled out
            if time.time() >= session_end_time:
                self.logger.info("Session timed out.")

            self.link.disconnect()
            self.logger.info("Session ended.")

        self.destroy_link()
        return

