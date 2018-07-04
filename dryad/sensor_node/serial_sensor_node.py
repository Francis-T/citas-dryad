#   Serial Communication for Sensor Data
#   Author: Jerelyn C
#
#   Serial communication between the microcontroller and AGN

import time
import serial
import logging
import json
import dryad.sys_info as sys_info

from serial.threaded import *

from time import time, sleep, ctime
from abc import ABCMeta, abstractmethod

from dryad.sensor_node.base_sensor_node import BaseSensorNode
from dryad.sensor_node.read_thread import ReadThread

PORT = '/dev/ttyUSB0'
BAUD_RATE = 9600

MAX_SAMPLE_COUNT = 10            # Max number of samples
MAX_SAMPLING_DURATION = 60.0 * 1.0    # TODO 5-minute max sampling duration
MAX_CONN_RETRIES = 60
CONN_ATTEMPT_TIMEOUT = 35.0
CONN_ATTEMPT_INTERVAL = 0.1
READ_INTERVAL = 20.0          # Number of seconds between reads


class SerialSensorNode(BaseSensorNode, metaclass=ABCMeta):
    def __init__(self, node_name, node_address, event_read_complete):
        self.logger = logging.getLogger(
            "main.serial_sensor_node.SerialSensorNode")
        BaseSensorNode.__init__(self, node_name, node_address)
        self.event_read_complete = event_read_complete

        self.read_thread = None

        self.ser = serial.Serial(PORT, baudrate=BAUD_RATE, timeout=None)
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
        self.logger.debug("[{}] Connected to serial port {}".format(self.get_name(), self.ser.name))
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

    def gather_data(self, on_error_flag=None, on_read_flag=None):
        reading = None
        try:
            reading = self.ser.readline().decode("utf-8").strip()
            if reading.startswith('{') and reading.endswith('}'):
                reading = eval(reading)
        except Exception as e:
            self.logger.error("Exception occured {}".format(str(e)))

        self.logger.debug("Data received {}".format(reading))
        return reading

    def stop(self):
        self.logger.debug("[{}] Stop called".format(self.get_name()))
        self.ser.close()
        
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
