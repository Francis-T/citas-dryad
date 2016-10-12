from bluepy.btle import DefaultDelegate, Peripheral, UUID
from threading import Event, Thread
from collections import defaultdict
from time import sleep, time
from pprint import pprint

import datetime
import traceback
import numpy as np
import utils.transform as transform
import logging


## Constants ##
# Services
SERVICES = {
    "LIVE"            : "39e1fa0084a811e2afba0002a5d5c51b",
    "BATTERY"        : 0x180f,
    "DEVICE_INFO"    : 0x180a
}

# Sensors Characteristics (Old firmware)
SENSORS = {
    "SUNLIGHT"        : "39e1fa0184a811e2afba0002a5d5c51b",
    "SOIL_EC"        : "39e1fa0284a811e2afba0002a5d5c51b",
    "SOIL_TEMP"        : "39e1fa0384a811e2afba0002a5d5c51b",
    "AIR_TEMP"        : "39e1fa0484a811e2afba0002a5d5c51b",
    "SOIL_MOISTURE"    : "39e1fa0584a811e2afba0002a5d5c51b",
}

# Sensors Characteristics (New firmware)
CAL_SENSORS = {
    "SUNLIGHT"        : "39e1fa0184a811e2afba0002a5d5c51b",
    "SOIL_EC"        : "39e1fa0284a811e2afba0002a5d5c51b",
    "SOIL_TEMP"        : "39e1fa0384a811e2afba0002a5d5c51b",
    "AIR_TEMP"        : "39e1fa0484a811e2afba0002a5d5c51b",
    "VWC"            : "39e1fa0584a811e2afba0002a5d5c51b",
    "CAL_VWC"        : "39e1fa0984a811e2afba0002a5d5c51b",
    "CAL_AIR_TEMP"    : "39e1fa0a84a811e2afba0002a5d5c51b",
    "CAL_DLI"        : "39e1fa0b84a811e2afba0002a5d5c51b",
    "CAL_EA"        : "39e1fa0c84a811e2afba0002a5d5c51b",
    "CAL_ECB"        : "39e1fa0d84a811e2afba0002a5d5c51b",
    "CAL_EC_POROUS"    : "39e1fa0e84a811e2afba0002a5d5c51b",
}

# Control characteristics
CONTROLS = {
    "FIRMWARE_VER"        : 0x2a26,
    "LIVE_MODE_PERIOD"    : "39e1fa0684a811e2afba0002a5d5c51b",   
    "LED"                : "39e1fa0784a811e2afba0002a5d5c51b",
    "LAST_MOVE_DATE"    : "39e1fa0884a811e2afba0002a5d5c51b", 
    "BATTERY_LEVEL"        : 0x2a19
}

MAX_CONN_RETRIES = 20

FLAG_NOTIF_ENABLE   = "\x01\x00"
FLAG_NOTIF_DISABLE  = "\x00\x00"

DEBUG_RAW_DATA = True


class ReadThread(Thread):
    def __init__(self, pdevice, event, read_sample_size):
        Thread.__init__(self)
        self.pdevice = pdevice
        self.hevent = event
        self.logger = logging.getLogger("main.parrot_ble.ReadThread")

        self.readings = []
        self.readings_left = read_sample_size
        return

    def run(self):
        if self.pdevice == None:
            self.logger.error("No device")
            self.hevent.set()
            return False
        
        if self.pdevice.is_connected == False:
            res = self.pdevice.connect()
            if (res == False):
                self.logger.error("Cannot read from unconnected device")
                self.hevent.set()
                return False

        # Setup the 'connection'
        self.pdevice.setup_conn()

        while self.readings_left > 0:
            # Retrieve the readings
            reading = self.pdevice.read_sensors(sensors=["SOIL_TEMP", "AIR_TEMP", "CAL_AIR_TEMP"])
            
            out_str = "[{}] ".format(self.pdevice.ble_name)
            for key, val in reading.items():
                out_str += "{} = {:.2f}, ".format(key, val)

            self.logger.info(out_str)

            self.readings.append( reading )
            self.readings_left -= 1
            sleep(1.0)

        self.logger.info("Finished reading")

        self.hevent.set()

        self.pdevice.stop()

        return True

    def get_readings(self):
        return self.readings

# Parrot class    
class Parrot():    
    def __init__(self, address, name, event):
        self.ble_name = name
        self.ble_addr = address
        self.pdevice = None
        self.pdelegate = None
        self.is_connected = False

        self.hevent = event

        self.read_sample_size = 10
        self.live_measure_period = "\x01"
        self.isNewFirmware = True
        self.live_service = None
        self.battery_service = None

        self.read_thread = None

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
            if ( elapsed_time > 35.0 ):
                self.logger.debug("Connect attempt took {} secs".format(elapsed_time))
                self.logger.warning("Connect attempt exceeds threshold. Is the device nearby?")
                break

            retries += 1

            sleep(6.0 + 1.0 * retries)
            self.logger.debug("Attempting to connect ({})...".format(retries))

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
    def start(self):
        if self.read_thread == None:
            self.read_thread = ReadThread(self, self.hevent, self.read_sample_size)
            self.read_thread.start()

        return True

    # @desc     Stops an ongoing sensor read operation
    # @return   A boolean indicating success or failure
    def stop(self):
        if (self.is_connected == False):
            self.logger.info("Already stopped")
            return True

        # TODO Disconnect from the device ?
        self.disconnect()
        
        return True

    ## -------------- ##
    ## Misc Functions ##
    ## -------------- ##
    # @desc     Set the number of samples per read session
    # @return   None
    def set_read_sample_size(self, sample_size):
        self.read_sample_size = sample_size
        return

    def get_readings(self):
        if not self.read_thread == None:
            return self.read_thread.get_readings()

        return None

    def set_live_measure_period(self):
        # turning on live measure period, 1s
        live_measure_ch = self.live_service.getCharacteristics(UUID(CONTROLS["LIVE_MODE_PERIOD"]))[0]
        live_measure_ch.write(str.encode(self.live_measure_period))
        
    def switch_led(self, state):
        led_control_ch = self.live_service.getCharacteristics(UUID(CONTROLS["LED"]))[0]
        led_control_ch.write(str.encode(state))
    
    # returns whether parrot flower is the new version or not
    def checkFirmware(self, firmware_version):
        new_firmware_version = '1.1.0'
        ver_number = firmware_version.decode("utf-8").split("_")[1].split("-")[1]
        self.isNewFirmware = ver_number == new_firmware_version

    def add_timestamp(self, data):
        data["PF_TIMESTAMP"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return data    
    

    # returns dictionary of sensor readings from parrot flower 
    def read_sensors(self, sensors=["SUNLIGHT", "SOIL_EC", "SOIL_TEMP", "AIR_TEMP", "VWC", "CAL_VWC", "CAL_AIR_TEMP", "CAL_DLI", "CAL_EA", "CAL_ECB", "CAL_EC_POROUS", "BATTERY"]):
        tr = transform.DataTransformation()
        
        reading = dict.fromkeys(sensors)

        battery_level_ch = self.battery_service.getCharacteristics(UUID(CONTROLS["BATTERY_LEVEL"]))[0]
        battery_level = 0
        
        try:
            # conversion from byte to decimal
            battery_level = ord(battery_level_ch.read())
            if "BATTERY" in reading.keys():
                reading["BATTERY"] = battery_level
        except Exception as err:
            self.logger.exception(traceback.print_tb(err.__traceback__))

        self.switch_led(FLAG_NOTIF_ENABLE)

        # iterate over the calibrated sensors characteristics
        for key, val in CAL_SENSORS.items():
            if key not in sensors:
                # Skip all sensors we aren't reading this time
                continue
                
            char = self.live_service.getCharacteristics(UUID(val))[0]    
            if char.supportsRead(): 
                try:
                    if DEBUG_RAW_DATA and (key in ["SUNLIGHT", "SOIL_EC", "AIR_TEMP", "SOIL_TEMP", "VWC"]):
                        reading[key] = tr.unpack_U16(char.read())
                    elif not DEBUG_RAW_DATA:
                        if key == "SUNLIGHT":
                            reading[key] = tr.conv_light(tr.unpack_U16(char.read()))
                        elif key == "SOIL_EC":
                            reading[key] = tr.conv_ec(tr.unpack_U16(char.read()))
                        elif key in ["AIR_TEMP", "SOIL_TEMP"]:
                            reading[key] = tr.conv_temp(tr.unpack_U16(char.read()))
                        elif key == "VWC":
                            reading[key] = tr.conv_moisture(tr.unpack_U16(char.read()))
                    else:
                        reading[key] = tr.decode_float32(char.read())
                except:
                    self.logger.error("Failed to read and decode sensor data: " + str(char))

        self.switch_led(FLAG_NOTIF_DISABLE)
        
        return reading    

    # returns aggregated (averaged) readings
    def get_agg_readings(self):
        # getting readings for N_READ times (3 times)        
        readings = np.array()
        temp_counter = self.n_read
        while temp_counter != 0:
            readings = np.append(readings, self.read_sensors())
            temp_counter -= 1    
        
        aggregated_data = defaultdict(int)
        for entry in readings:    
            for key in entry.keys():
                aggregated_data[key] += float(entry[key])
        data = {k: v / self.n_read for k, v in aggregated_data.items()} 
        return self.add_timestamp(data)    
        
    def setup_conn(self): 
        # getting firmware version of parrotflower        
        device_info_service = self.pdevice.getServiceByUUID(UUID(SERVICES["DEVICE_INFO"]))
        firmware_ver_ch = device_info_service.getCharacteristics(UUID(CONTROLS["FIRMWARE_VER"]))[0]
        
        # check firmware
        self.checkFirmware(firmware_ver_ch.read())

        # getting live services and controlling led and live measure period
        self.live_service = self.pdevice.getServiceByUUID(UUID(SERVICES["LIVE"]))  
        # setting live measure period
        self.set_live_measure_period()    
    
        # getting pf battery service
        self.battery_service = self.pdevice.getServiceByUUID(UUID(SERVICES["BATTERY"]))

        return True


    def disconnect(self):
        try:
            self.pdevice.disconnect()
        except Exception as e:
            self.logger.error("Stop device failed: " + str(e))

        return

