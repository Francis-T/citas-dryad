#   Serial Communication for Sensor Data
#   Author: Jerelyn C
#
#   Serial communication between the microcontroller and AGN

import time
import serial
import logging
import dryad.sys_info as sys_info

from time import time, sleep, ctime

from abc import ABCMeta, abstractmethod
from dryad.sensor_node.base_sensor_node import BaseSensorNode
from dryad.sensor_node.read_thread import ReadThread

PORT = '/dev/ttyACM0'
BAUD_RATE = 115200

MAX_SAMPLE_COUNT = 10            # Max number of samples
MAX_SAMPLING_DURATION = 60.0 * 1.0    # TODO 5-minute max sampling duration
MAX_CONN_RETRIES = 60
CONN_ATTEMPT_TIMEOUT = 35.0
CONN_ATTEMPT_INTERVAL = 0.1
READ_INTERVAL = 20.0          # Number of seconds between reads


class SerialReadThread(ReadThread):
    def __init__(self, func_read, readings, logger=None, event_done=None,
                 event_read=None, event_error=None, read_samples=0, read_time=0,
                 read_interval=0):
        logger = logging.getLogger("main.bluno_sensor_node.BlunoReadThread")
        ReadThread.__init__(self, func_read, readings, logger, event_done, event_read,
                            event_error, read_samples, read_time, read_interval)
        return

    def run(self):
        try:
            self.read_time = time() + self.read_time
            ser = serial.Serial(PORT, BAUD_RATE)

            while self.should_continue_read():
                reading = ser.readline()
                if reading != None:
                    self.cache_reading(reading)
                    self.notify_read()
                    time.sleep(self.read_interval)
            self.logger.info("[{}] Finished QREAD".format("[NodeName]"))
        self.notify_done()

        return True


class SerialSensorNode(BaseSensorNode, metaclass=ABCMeta):
    def __init__(self, node_name, node_address, event_read_complete):
        self.logger = logging.getLogger(
            "main.serial_sensor_node.SerialSensorNode")
        self.event_read_complete = event_read_complete

        self.readings = []

        self.max_conn_retries = MAX_CONN_RETRIES
        self.conn_attempt_timeout = CONN_ATTEMPT_TIMEOUT
        self.conn_attempt_interval = CONN_ATTEMPT_INTERVAL
        self.max_sample_count = MAX_SAMPLE_COUNT
        self.max_sampling_duration = MAX_SAMPLING_DURATION
        self.read_interval = READ_INTERVAL

        # Load params from database instead of using defaults
        self.reload_system_params()

    def start(self):
        if self.read_thread == None:
            self.read_thread = SerialReadThread(parent=self,
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

    def get_latest_readings(self):
        return self.readings

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
            sys_info.set_param("CONN_ATTEMPT_TIMEOUT",
                               str(CONN_ATTEMPT_TIMEOUT))

        records = sys_info.get_param("CONN_ATTEMPT_INTERVAL")
        if records != False:
            self.conn_attempt_interval = float(records[0].value)
        else:
            sys_info.set_param("CONN_ATTEMPT_INTERVAL",
                               str(CONN_ATTEMPT_INTERVAL))

        records = sys_info.get_param("MAX_SAMPLE_COUNT")
        if records != False:
            self.max_sample_count = int(records[0].value)
        else:
            sys_info.set_param("MAX_SAMPLE_COUNT", str(MAX_SAMPLE_COUNT))

        records = sys_info.get_param("MAX_SAMPLING_DURATION")
        if records != False:
            self.max_sampling_duration = float(records[0].value)
        else:
            sys_info.set_param("MAX_SAMPLING_DURATION",
                               str(MAX_SAMPLING_DURATION))

        records = sys_info.get_param("READ_INTERVAL")
        if records != False:
            self.read_interval = float(records[0].value)
        else:
            sys_info.set_param("READ_INTERVAL", str(READ_INTERVAL))

        return
    ## --------------- ##
    ## Sensor Requests ##
    ## --------------- ##

    # @desc     Sends a request to the sensor through serial
    # @return   A boolean indicating success or failure
    def request(self, serial, contents):
        if serial == None:
            return False

        try:
            serial.write(str.encode(contents))
            self.logger.debug("[{}] Sent data: {}".format(
                self.get_name(), contents))
        except Exception as err:
            self.logger.exception(err)
            return False

        return True

    def req_deploy(self, serial):
        return self.request(serial, "QDEPL;\r\n")

    def req_undeploy(self, serial):
        return self.request(serial, "QUNDP;\r\n")

    def req_start_read(self, serial):
        return self.request(serial, "QREAD;\r\n")

    def req_stop_read(self, serial):
        return self.request(serial, "QSTOP;\r\n")
