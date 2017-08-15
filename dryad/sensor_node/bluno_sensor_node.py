#
#   Bluno Sensor Node
#   Author: Francis T
#
#   Class for interfacing the Aggregator Node with a Parrot Flower Power 
#   Soil Sensor
#
import time
import logging
import utils.transform as transform

from dryad.sensor_node.ble_sensor_node import BleSensorNode
from dryad.sensor_node.read_thread import ReadThread
from threading import Event
from bluepy.btle import DefaultDelegate, Peripheral, UUID, BTLEException

## CONSTANTS ##
SERVICES = {
    "CTRL": "0000dfb000001000800000805f9b34fb",
    "DEVINFO": "0000180a00001000800000805f9b34fb"
}

CTRL_CHARS = {
    "SERIAL": "0000dfb100001000800000805f9b34fb",
    "COMMAND": "0000dfb200001000800000805f9b34fb"
}


DEVINFO_CHARS = {
    "MODEL_NO": "00002a2400001000800000805f9b34fb",
    "NAME": "00002a0000001000800000805f9b34fb"
}

SERIAL_HDL = 37
MAX_CONN_RETRIES = 40  # old number was 10

DEBUG_RAW_DATA = True

# Security variables
DFR_PWD_STR = str(bytearray(b"AT+PASSWOR=DFRobot\r\n"))
DFR_BDR_STR = str(bytearray(b"AT+CURRUART=115200\r\n"))

class PeripheralDelegate(DefaultDelegate):
    def __init__(self, peripheral, dvc_name, serial_channel, event_done=None):
        DefaultDelegate.__init__(self)
        self.peripheral = peripheral
        self.serial_ch = serial_channel
        self.event_done = event_done
        self.logger = logging.getLogger("main.bluno_ble.PeripheralDelegate")

        self.last_reading = None

        return

    def handleNotification(self, cHandle, data):
        data = str(data.decode("utf-8"))

        if cHandle is SERIAL_HDL:
            if "RUNDP:OK" in data:
                self.logger.info("[{}] Bluno: Undeployed".format(self.peripheral.get_name()))

            if "RDEPL:OK" in data:
                self.logger.info("[{}] Bluno: Deployed".format(self.peripheral.get_name()))

            if "RDEND:OK" in data:
                self.notify_done()

            if "pH" in data:
                tr = transform.DataTransformation()

                ph_data = data.split("=")[1].split(";")[0].strip()

                try:
                    if DEBUG_RAW_DATA == False:
                        ph_data = tr.conv_ph(float(ph_data))
                except:
                    self.logger.error("[{}] Cannot convert ph data ({}) to float".format(
                        self.peripheral.get_name(), ph_data))
                    self.notify_error()
                    return
                self.last_reading = {"ph": ph_data, "ts": int(time.time()) }

            if "bt" in data:
                batt_data = data.split("=")[1].split(";")[0].strip()
                self.last_reading = {"bl_battery": batt_data, "ts": int(time.time()) }

            self.logger.debug("[{}] Received: {}".format( self.peripheral.get_name(), str(data) ))

        return

    def get_last_reading(self):
        last_reading = self.last_reading
        self.last_reading = None
        return last_reading

class BlunoReadThread(ReadThread):
    def __init__(self, parent, func_read, readings, logger=None, event_done=None, event_read=None, \
                 event_error=None, read_samples=0, read_time=0, read_interval=0):
        logger = logging.getLogger("main.bluno_sensor_node.BlunoReadThread")
        ReadThread.__init__(self, parent, func_read, readings, logger, event_done, event_read, \
                            event_error, read_samples, read_time, read_interval)
        self.pdelegate = None
        return

    def run(self):
        if self.parent == None:
            self.logger.error("No parent device".format())
            self.notify_error()
            self.notify_done()
            return False
        
        # Attempt to connect the parent device if it has not been connected yet
        if (self.parent.is_connected == False):
            res = self.parent.connect()
            if (res == False):
                self.logger.error("[{}] Cannot read from unconnected device".format(self.parent.get_name()))
                self.notify_error()
                self.notify_done()
                return False

        # Setup the BLE peripheral delegate
        serial_ch = self.parent.get_serial()
        
        event_done = Event()
        event_read = Event()
        event_error = Event()

        self.pdelegate = PeripheralDelegate(peripheral=self.parent,
                                            dvc_name=self.parent.get_name(),
                                            serial_channel=serial_ch,
                                            event_done=event_done)

        peripheral = self.parent.get_peripheral()
        peripheral.setDelegate(self.pdelegate)

        try:
            # This is preserved for old sensor node versions
            self.parent.req_deploy(serial_ch)
            peripheral.waitForNotifications(1.0)

            # Send QREAD requests through the Serial
            ns = 0
            self.read_time = time.time() + self.read_time
            while self.should_continue_read():
                self.parent.req_start_read(serial_ch)
                peripheral.waitForNotifications(2.0)
                ns += 1
                
                reading = self.pdelegate.get_last_reading()
                if reading != None:
                    self.cache_reading(reading)
                    self.notify_read()
                    time.sleep(self.read_interval)

            self.logger.info("[{}] Finished QREAD".format(self.parent.get_name()))

            if (self.parent.is_connected == False):
                self.notify_done()
                return True

            self.parent.req_undeploy(serial_ch)
            peripheral.waitForNotifications(1.0)

        except Exception as e:
            self.logger.exception("Exception occurred: {}".format(str(e)))

        self.notify_done()

        return True


class BlunoSensorNode(BleSensorNode):
    def __init__(self, node_id, node_address, event_read_complete):
        logger = logging.getLogger("main.bluno_sensor_node.BlunoSensorNode")
        BleSensorNode.__init__(self, node_id, node_address, logger, \
                               event_read_complete=event_read_complete)

        self.live_measure_period = "\x01"
        return

    def start(self):
        if self.read_thread == None:
            self.read_thread = BlunoReadThread(parent=self,
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
            # Send a QSTOP request through the Serial
            serial_ch = self.get_serial()
            res = False

            try:
                res = self.req_stop_read(serial_ch)
            except Exception as e:
                self.logger.exception(e)
        
        return BleSensorNode.stop(self)

    def gather_data(self, on_error_flag=None, on_read_flag=None):
        return None

    def setup_connection(self): 
        # TODO
        print("DUMMY FUNCTION")
        return False

    # @desc     Returns the serial characteristic
    # @return   A Characteristic object representing the Serial characteristic
    def get_serial(self):
        serial_ch = None
        try:
            ctrl_service = self.peripheral.getServiceByUUID(
                UUID(SERVICES["CTRL"]))
            serial_ch = ctrl_service.getCharacteristics(
                UUID(CTRL_CHARS["SERIAL"]))[0]
        except Exception as err:
            self.logger.exception(err)
            return None

        return serial_ch

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
            self.logger.debug("[{}] Sent data: {}".format(self.get_name(), contents))
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
    

