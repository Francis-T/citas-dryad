from bluepy.btle import Peripheral, UUID, DefaultDelegate
from threading import Event
from collections import defaultdict 
from time import sleep, time

import datetime
import traceback
import numpy as np
import logging

## CONSTANTS ##
SERVICES = {
    "CTRL"        : "0000dfb000001000800000805f9b34fb",
    "DEVINFO"    : "0000180a00001000800000805f9b34fb"
}

CTRL_CHARS = {
    "SERIAL"    : "0000dfb100001000800000805f9b34fb",
    "COMMAND"    : "0000dfb200001000800000805f9b34fb"
}


DEVINFO_CHARS = {
    "MODEL_NO"    : "00002a2400001000800000805f9b34fb",
    "NAME"        : "00002a0000001000800000805f9b34fb"  
}

SERIAL_HDL = 37

MAX_CONN_RETRIES = 10

# Security variables
DFR_PWD_STR = str(bytearray(b"AT+PASSWOR=DFRobot\r\n"))
DFR_BDR_STR = str(bytearray(b"AT+CURRUART=115200\r\n"))

class PeripheralDelegate(DefaultDelegate):
    def __init__(self, pdevice, serial_ch, event, read_samples, read_until):
        DefaultDelegate.__init__(self)
        self.pdevice = pdevice
        self.serial_ch = serial_ch
        self.hevent = event
        self.logger = logging.getLogger("main.bluno_ble.PeripheralDelegate")

        self.readings = np.array([])
        self.readings_left = read_samples
        self.read_until = read_until

        self.is_reading = True

        return

    def handleNotification(self, cHandle, data):
        data = str(data)
        if cHandle is SERIAL_HDL:
            if "RUNDP:OK" in data:
                self.logger.info("Bluno: Undeployed")

            if "RDEPL:OK" in data:
                self.logger.info("Bluno: Deployed")

            if "RDEND:OK" in data:
                if (self.readings_left > 0):
                    self.pdevice.req_start_read(self.serial_ch)

            if "pH" in data:
                if self.is_reading == False:
                    return

                ph_data = data.split("=")[1].split(";")[0].strip()
                self.readings = np.append( self.readings,
                                           { "PH": ph_data,
                                             "ts" : int(time()) } )
                # self.readings = np.append( self.readings, float(data.split("=")[1].split(";")[0].strip()))
                self.logger.info( "[BLUNO] pH = {}".format(ph_data) )

                # Decrease the number of readings
                self.readings_left -= 1

                # Once the desired limit of readings are reached, trigger the
                #   handle event to signal that the contents can now be taken
                if (self.should_continue_read() == False):
                    self.is_reading = False
                    self.hevent.set()

        return

    def should_continue_read(self):
        # If we're no longer connected, then stop reading
        if self.pdevice.is_connected == False:
            return False

        # If the current time exceeds our read until value,
        #   then return False immediately to stop reading
        if (self.read_until > 0) and (time() > self.read_until):
            self.logger.debug("Read time limit exceeded")
            return False
            
        # Otherwise, check if the limit of readings has been
        #   reached and return False to stop reading
        if self.readings_left <= 0:
            self.logger.debug("Read sample limit exceeded")
            return False

        # Allow reading to continue otherwise
        return True

    # @desc     Returns the collected sensor readings to the calling function
    # @return   A numpy array containing the collected readings
    def get_readings(self):
        return self.readings

class Bluno():
    def __init__(self, address, name, event):
        self.ble_name = name
        self.ble_addr = address
        self.pdevice = None
        self.pdelegate = None
        self.is_connected = False

        self.hevent = event

        self.read_sample_size = 10
        self.logger = logging.getLogger("main.parrot_ble.Parrot")

        return

    ## ---------------- ##
    ## Public Functions ##
    ## ---------------- ##

    # @desc     Manually triggers connection to this sensor
    # @return   A boolean indicating success or failure
    def connect(self):
        self.logger.info("Attempting to connect to {} [{}]".format(self.ble_name, self.ble_addr))
        retries = 0

        # Attempt to connect to the peripheral device a few times
        is_connected = True
        start_time = time()
        while (self.pdevice is None) and (retries < MAX_CONN_RETRIES):
            is_connected = True

            conn_attempt_time = time()
            try:
                self.pdevice = Peripheral(self.ble_addr, "public")
            except Exception as err:
                is_connected = False

            elapsed_time = time() - conn_attempt_time

            # Leave the loop immediately if we're already connected
            if ( is_connected ):
                self.logger.debug("Overall connect time: {} secs".format(time() - start_time))
                break

            # Put out a warning and cut down retries if our connect attempt exceeds thresholds
            if ( elapsed_time > 30.0 ):
                self.logger.debug("Connect attempt took {} secs".format(elapsed_time))
                self.logger.warning("Connect attempt exceeds threshold. Is the device nearby?")
                break

            retries += 1

            sleep(6.0 + 1.0 * retries)
            self.logger.info("Attempting to connect ({})...".format(retries))

        # Check if connected
        if (is_connected == False):
            self.is_connected = False
            self.logger.error("Failed to connect to device")
        else:
            self.is_connected = True
            self.logger.info("Connected.")

        return self.is_connected

    # @desc     Starts a read operation on this sensor
    # @return   A boolean indicating success or failure
    def start(self, time_limit=0):
        # Ensure that we are connected
        if (self.is_connected == False):
            res = self.connect()
            if (res == False):
                self.logger.error("Cannot read from unconnected device")
                return False
        
        # Setup the BLE peripheral delegate
        serial_ch = self.get_serial()
        self.pdelegate = PeripheralDelegate(self, 
                                            serial_ch=serial_ch,
                                            event=self.hevent,
                                            read_samples=self.read_sample_size,
                                            read_until=time_limit )
        self.pdevice.setDelegate( self.pdelegate )
        
        # TODO This shouldn't be here in the future since we expect the
        #      sensor node to preserve its deployment state in-between
        #      bootups
        self.req_deploy(serial_ch)
        self.pdevice.waitForNotifications(1.0)

        # Send a QREAD request through the Serial
        res = self.req_start_read(serial_ch)
        if (res == False):
            return False
        self.pdevice.waitForNotifications(1.0)
        self.pdevice.waitForNotifications(1.0)

        ns = 0
        while ns < self.read_sample_size:
            self.pdevice.waitForNotifications(2.0)
            ns += 1

        return True

    # @desc     Stops an ongoing sensor read operation
    # @return   A boolean indicating success or failure
    def stop(self):
        if (self.is_connected == False):
            self.logger.info("Already stopped")
            return True

        # Send a QSTOP request through the Serial
        serial_ch = self.get_serial()
        res = self.req_stop_read(serial_ch)
        if (res == False):
            return False

        # TODO Disconnect from the device ?
        self.pdevice.disconnect()
        
        return True

    ## -------------- ##
    ## Misc Functions ##
    ## -------------- ##

    # @desc     Returns the serial characteristic
    # @return   A Characteristic object representing the Serial characteristic
    def get_serial(self):
        serial_ch = None
        try:
            ctrl_service = self.pdevice.getServiceByUUID(UUID(SERVICES["CTRL"]))
            serial_ch = ctrl_service.getCharacteristics( UUID(CTRL_CHARS["SERIAL"]) )[0]
        except Exception as err:
            self.logger.exception(err)
            return None

        return serial_ch
    
    # @desc     Set the number of samples per read session
    # @return   None
    def set_read_sample_size(self, sample_size):
        self.read_sample_size = sample_size
        return

    # @desc     Gets the readings from the Peripheral Delegate
    # @return   A numpy array containing the collected readings
    def get_readings(self):
        if (self.pdelegate == None):
            return None

        return self.pdelegate.get_readings()

    def get_readings_mean_var(self):
        readings = self.get_readings()
        if readings.size == 0:
            return (0, 0) 
        return (np.round(readings.mean(), 4), np.round(readings.var(),4))
    
    def get_agg_readings(self):
        aggregated_data = defaultdict(int)
        data = self.get_readings()
        for entry in data:
            aggregated_data["PH"] += float(entry["PH"])
        data = {k: v / self.n_read for k, v in aggregated_data.items()} 
        return self.add_timestamp(data)        

    def isSuccess(self):
        return self.isSuccess

    def add_timestamp(self, data):
        data["BL_TIMESTAMP"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return data    

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



