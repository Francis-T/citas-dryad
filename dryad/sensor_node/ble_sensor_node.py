#
#   Bluetooth LE Sensor Node Abstract Class
#   Author: Francis T
#
#   Abstract Class for interfacing with a Bluetooth LE capable sensor node
#
import time
import logging
import dryad.sys_info as sys_info

from abc import ABCMeta, abstractmethod
from dryad.sensor_node.base_sensor_node import BaseSensorNode
from dryad.sensor_node.read_thread import ReadThread
from bluepy.btle import Scanner, DefaultDelegate, Peripheral, UUID, BTLEException

ADTYPE_LOCAL_NAME = 9

MAX_SAMPLE_COUNT        = 10            # Max number of samples
MAX_SAMPLING_DURATION   = 60.0 * 1.0    # TODO 5-minute max sampling duration
MAX_CONN_RETRIES        = 60
CONN_ATTEMPT_TIMEOUT    = 35.0
CONN_ATTEMPT_INTERVAL   = 0.1
READ_INTERVAL           = 20.0          # Number of seconds between reads

class BleSensorNode(BaseSensorNode, metaclass=ABCMeta):
    def __init__(self, node_name, node_address, logger, event_read_complete):
        BaseSensorNode.__init__(self, node_name, node_address)
        self.logger = logger
        self.event_read_complete = event_read_complete

        self.peripheral = None
        self.read_thread = None
        self.is_connected = False
        self.readings = []

        self.max_conn_retries       = MAX_CONN_RETRIES
        self.conn_attempt_timeout   = CONN_ATTEMPT_TIMEOUT
        self.conn_attempt_interval  = CONN_ATTEMPT_INTERVAL
        self.max_sample_count       = MAX_SAMPLE_COUNT
        self.max_sampling_duration  = MAX_SAMPLING_DURATION
        self.read_interval          = READ_INTERVAL

        # Load params from database instead of using defaults
        self.reload_system_params()

        return

    def connect(self):
        # Update the state
        self.set_state("CONNECTING")

        if self.get_address() == None or self.get_address() == "":
            self.logger.info("Cannot connect to {}/{}".format(self.get_name(), self.get_address()))
            return False

        self.logger.info("[{}] Attempting to connect to {}".format(self.get_name(), self.get_address()))

        retries = 0
        is_connected = False
        start_time = time.time()

        while (self.peripheral is None) and (retries < self.max_conn_retries):
            conn_success = True
            conn_attempt_time = time.time()

            try:
                self.peripheral = Peripheral(self.get_address(), "public")
            except Exception as e:
                self.logger.error("[{}] Connecton failed: {}".format(self.get_name(), e.message))
                conn_success = False

            elapsed_time = time.time() - conn_attempt_time

            # End the loop if connection is successful
            if conn_success:
                self.logger.debug("[{}] Overall connect time: {} secs, Total retries: {}".format(self.get_name(), time.time() - start_time, retries))
                is_connected = True
                break

            # Put out a warning and cut down retries if our connect attempt exceeds thresholds
            if elapsed_time > self.conn_attempt_timeout:
                self.logger.debug("[{}] Connect attempt took {} secs".format(self.get_name(), elapsed_time))
                self.logger.warning("[{}] Connect attempt exceeds threshold. Is the device nearby?".format(self.get_name()))
                break

            retries += 1

            time.sleep(self.conn_attempt_interval)
            self.logger.debug("[{}] Attempting to connect ({})...".format(self.get_name(), retries))

        # Check if a successful connection was established
        if (is_connected):
            # Update the state
            self.set_state("CONNECTED")
            self.is_connected = True
            self.logger.info("[{}] Connected.".format(self.get_name()))

            return True

        # Otherwise, indicate that a connection problem has occurred
        self.set_state("INACTIVE")
        self.is_connected = False
        self.logger.error("[{}] Failed to connect to device".format(self.get_name()))

        return False

    def start(self):
        if self.read_thread == None:
            self.read_thread = ReadThread(parent=self,
                                          func_read=self.gather_data,
                                          readings=self.readings,
                                          event_done=self.event_read_complete,
                                          read_samples=self.max_sample_count,
                                          read_time=self.max_sampling_duration,
                                          read_interval=self.read_interval)
            self.read_thread.start()

        return True

    def stop(self):
        self.logger.debug("[{}] Stop called".format(self.get_name()))
        if (self.is_connected == True):
            # Disconnect from the device
            self.disconnect()
        else:
            self.logger.info("[{}] Already stopped".format(self.get_name()))

        # Wait for active read threads to finish
        if self.read_thread != None:
            return True

        if threading.current_thread == self.read_thread:
            return True

        if self.read_thread.is_alive() == True:
            self.read_thread.join(30.0)
        
        return True

    def disconnect(self):
        try:
            self.peripheral.disconnect()
        except Exception as e:
            self.logger.error("[{}] Stop device failed: ".format(self.get_name(), str(e)))

        self.is_connected = False

        return

    def get_latest_readings(self):
        return self.readings

    def scan(self):
        scanner = Scanner()
        self.logger.info("Scanning for devices...")
        scanned_devices = scanner.scan(20.0)
        self.logger.info("Scan finished")
        
        scanned_str = ""
        for device in scanned_devices:
            node_id = device.getValueText( ADTYPE_LOCAL_NAME )
            if node_id == None:
                continue

            scanned_str +=  node_id + " | "

        self.logger.info("    " + scanned_str)
            
        return scanned_devices

    def get_peripheral(self):
        return self.peripheral
    
    def reload_system_params(self):
        records = sys_info.get_param("MAX_CONN_RETRIES")
        if records != False:
            self.max_conn_retries = int(records[0].value)
        else:
            sys_info.set_param("MAX_CONN_RETRIES", str(MAX_CONN_RETRIES))

        records = sys_info.get_param("CONN_ATTEMPT_TIMEOUT")
        if records != False:
            self.conn_attempt_timeout = float(records[0].value)
        else:
            sys_info.set_param("CONN_ATTEMPT_TIMEOUT", str(CONN_ATTEMPT_TIMEOUT))

        records = sys_info.get_param("CONN_ATTEMPT_INTERVAL")
        if records != False:
            self.conn_attempt_interval = float(records[0].value)
        else:
            sys_info.set_param("CONN_ATTEMPT_INTERVAL", str(CONN_ATTEMPT_INTERVAL))

        records = sys_info.get_param("MAX_SAMPLE_COUNT")
        if records != False:
            self.max_sample_count = int(records[0].value)
        else:
            sys_info.set_param("MAX_SAMPLE_COUNT", str(MAX_SAMPLE_COUNT))


        records = sys_info.get_param("MAX_SAMPLING_DURATION")
        if records != False:
            self.max_sampling_duration = float(records[0].value)
        else:
            sys_info.set_param("MAX_SAMPLING_DURATION", str(MAX_SAMPLING_DURATION))

        records = sys_info.get_param("READ_INTERVAL")
        if records != False:
            self.read_interval = float(records[0].value)
        else:
            sys_info.set_param("READ_INTERVAL", str(READ_INTERVAL))

        return

    @abstractmethod
    def setup_connection(self):
        pass

    @abstractmethod
    def gather_data(self):
        pass


