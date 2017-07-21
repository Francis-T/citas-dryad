#
#   Parrot Sensor Node
#   Author: Francis T
#
#   Class for interfacing the Aggregator Node with a Parrot Flower Power 
#   Soil Sensor
#
import time
import logging
import utils.transform as transform

from dryad.database import DryadDatabase
from dryad.sensor_node.ble_sensor_node import BleSensorNode
from dryad.sensor_node.read_thread import ReadThread
from threading import Event
from bluepy.btle import DefaultDelegate, Peripheral, UUID, BTLEException

# Services
SERVICES = {
    "LIVE"           : "39e1fa0084a811e2afba0002a5d5c51b",
    "BATTERY"        : 0x180f,
    "DEVICE_INFO"    : 0x180a
}

# Sensors Characteristics (Old firmware)
SENSORS = {
    "sunlight"       : "39e1fa0184a811e2afba0002a5d5c51b",
    "soil_ec"        : "39e1fa0284a811e2afba0002a5d5c51b",
    "soil_temp"      : "39e1fa0384a811e2afba0002a5d5c51b",
    "air_temp"       : "39e1fa0484a811e2afba0002a5d5c51b",
    "vwc"            : "39e1fa0584a811e2afba0002a5d5c51b",
}

# Sensors Characteristics (New firmware)
CAL_SENSORS = {
    "sunlight"        : "39e1fa0184a811e2afba0002a5d5c51b",
    "soil_ec"        : "39e1fa0284a811e2afba0002a5d5c51b",
    "soil_temp"        : "39e1fa0384a811e2afba0002a5d5c51b",
    "air_temp"        : "39e1fa0484a811e2afba0002a5d5c51b",
    "vwc"            : "39e1fa0584a811e2afba0002a5d5c51b",
    "cal_vwc"        : "39e1fa0984a811e2afba0002a5d5c51b",
    "cal_air_temp"    : "39e1fa0a84a811e2afba0002a5d5c51b",
    "cal_dli"        : "39e1fa0b84a811e2afba0002a5d5c51b",
    "cal_ea"        : "39e1fa0c84a811e2afba0002a5d5c51b",
    "cal_ecb"        : "39e1fa0d84a811e2afba0002a5d5c51b",
    "cal_ec_porous"    : "39e1fa0e84a811e2afba0002a5d5c51b",
}

# Control characteristics
CONTROLS = {
    "FIRMWARE_VER"        : 0x2a26,
    "LIVE_MODE_PERIOD"    : "39e1fa0684a811e2afba0002a5d5c51b",   
    "LED"                : "39e1fa0784a811e2afba0002a5d5c51b",
    "LAST_MOVE_DATE"    : "39e1fa0884a811e2afba0002a5d5c51b", 
    "BATTERY_LEVEL"        : 0x2a19
}


FLAG_NOTIF_ENABLE   = "\x01\x00"
FLAG_NOTIF_DISABLE  = "\x00\x00"

DEBUG_RAW_DATA = False

class ParrotReadThread(ReadThread):
    def __init__(self, parent, func_read, readings, logger=None, event_done=None, event_read=None, \
                 event_error=None, read_samples=0, read_time=0, read_interval=0):
        logger = logging.getLogger("main.parrot_sensor_node.ParrotReadThread")
        ReadThread.__init__(self, parent, func_read, readings, logger, event_done, event_read, \
                            event_error, read_samples, read_time, read_interval)
        return

    def cache_reading(self, reading):
        node_name    = self.parent.get_name()
        node_address = self.parent.get_address()

        db = DryadDatabase()

        matched_devices = db.get_devices(address=node_address)
        node = matched_devices[0]

        print("Reading: {}".format(reading))
        result = db.insert_or_update_device( node.address, 
                                             node.node_id,
                                             node.device_type, 
                                             reading['pf_batt'] )
        db.close_session()

        if result == False:
            self.logger.error("Failed to save power reading")

        ReadThread.cache_reading(self, reading)
        return

class ParrotSensorNode(BleSensorNode):
    def __init__(self, node_id, node_address, event_read_complete):
        logger = logging.getLogger("main.ParrotSensorNode")
        BleSensorNode.__init__(self, node_id, node_address, logger, \
                               event_read_complete=event_read_complete)

        self.live_measure_period = "\x01"
        return

    def start(self):
        if self.read_thread == None:
            self.read_thread = ParrotReadThread(parent=self,
                                                func_read=self.gather_data,
                                                readings=self.readings,
                                                event_done=self.event_read_complete,
                                                read_samples=self.max_sample_count,
                                                read_time=self.max_sampling_duration,
                                                read_interval=self.read_interval)
            self.read_thread.start()

        return True


    def gather_data(self, on_error_flag=None, on_read_flag=None):
        sensors=[ "sunlight", "soil_temp", "air_temp", \
                  "vwc", "cal_vwc", "cal_air_temp", \
                  "cal_dli", "cal_ea", "cal_ecb", \
                  "cal_ec_porous", "pf_batt" ]

        tr = transform.DataTransformation()
        reading = dict.fromkeys(sensors)

        # Reading battery level from battery service
        battery_level_ch = self.battery_service.getCharacteristics(UUID(CONTROLS["BATTERY_LEVEL"]))[0]
        battery_level = 0
        
        try:
            # conversion from byte to decimal
            battery_level = ord(battery_level_ch.read())
            if "pf_batt" in reading.keys():
                reading["pf_batt"] = battery_level
        except Exception as err:
            #self.logger.exception(traceback.print_tb(err.__traceback__))
            self.logger.error("[{}] Exception occurred: {}".format(self.get_name(), str(err)))
            return None

        self.switch_led(FLAG_NOTIF_ENABLE)

        # iterate over the calibrated sensors characteristics
        for key, val in CAL_SENSORS.items():
            if key not in sensors:
                # Skip all sensors we aren't reading this time
                continue
            svchar_live = self.live_service.getCharacteristics(UUID(val)) 
            if len(svchar_live) <= 0:
                #self.logger.debug("No characteristic: {}, {}".format(key, val))
                continue

            char = svchar_live[0]
            if char.supportsRead(): 
                try:
                    if DEBUG_RAW_DATA and (key in ["sunlight", "soil_ec", "air_temp", "soil_temp", "vwc"]):
                        reading[key] = tr.unpack_U16(char.read())
                    elif not DEBUG_RAW_DATA:
                        if key == "sunlight":
                            reading[key] = tr.conv_light(tr.unpack_U16(char.read()))
                        elif key == "soil_ec":
                            reading[key] = tr.conv_ec(tr.unpack_U16(char.read()))
                            # Support cases where firmware is old
                            if reading["cal_dli"] == None:
                                reading["cal_dli"] = reading[key] 
                                reading["cal_ea"] = reading[key] 
                                reading["cal_ecb"] = reading[key] 
                                reading["cal_ec_porous"] = reading[key] 
                        elif key in "soil_temp":
                            reading[key] = tr.conv_temp(tr.unpack_U16(char.read()))
                        elif key == "air_temp": 
                            reading[key] = tr.conv_temp(tr.unpack_U16(char.read()))
                            # Support cases where firmware is old
                            if reading["cal_air_temp"] == None:
                                reading["cal_air_temp"] = reading[key] 
                        elif key == "vwc":
                            reading[key] = tr.conv_moisture(tr.unpack_U16(char.read()))
                            # Support cases where firmware is old
                            if reading["cal_vwc"] == None:
                                reading["cal_vwc"] = reading[key] 
                        else:
                            reading[key] = tr.decode_float32(char.read())
                                        
                except Exception as e:
                    self.logger.exception("[{}] Failed to read and decode sensor data: {}".format(str(self.get_name()), char.read()))

        reading['ts'] = int(time.time())
        self.switch_led(FLAG_NOTIF_DISABLE)

        return reading

    def setup_connection(self): 
        # getting firmware version of parrotflower        
        device_info_service = self.peripheral.getServiceByUUID(UUID(SERVICES["DEVICE_INFO"]))
        firmware_ver_ch = device_info_service.getCharacteristics(UUID(CONTROLS["FIRMWARE_VER"]))[0]
        firmware_ver_str = firmware_ver_ch.read()
        
        # check firmware
        new_firmware_version = '1.1.0'
        ver_number = firmware_ver_str.decode("utf-8").split("_")[1].split("-")[1]
        self.is_new_firmware = (ver_number == new_firmware_version)

        # setting live measure period
        self.set_live_measure_period()    
    
        # getting pf battery service
        self.battery_service = self.peripheral.getServiceByUUID(UUID(SERVICES["BATTERY"]))

        return True

    def set_live_measure_period(self):
        if self.peripheral == None:
            self.logger.error("[{}] Peripheral device unavailable".format(self.get_name()))
            return

        # getting live services and controlling led and live measure period
        self.live_service = self.peripheral.getServiceByUUID(UUID(SERVICES["LIVE"]))  

        # turning on live measure period, 1s
        live_measure_ch = self.live_service.getCharacteristics(UUID(CONTROLS["LIVE_MODE_PERIOD"]))[0]
        live_measure_ch.write(str.encode(self.live_measure_period))

        return

    def switch_led(self, state):
        led_control_ch = self.live_service.getCharacteristics(UUID(CONTROLS["LED"]))[0]
        led_control_ch.write(str.encode(state))
    

