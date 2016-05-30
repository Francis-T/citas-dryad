"""
    Name: parrot_ble.py
    Author: Francis T
    Description:
        Source code for the Parrot BLE controller
"""
import struct
import sys
import time
from math import pow

from bluetooth.ble import GATTRequester
from threading import Event

""" Constants """
UUID_NAME       = "00002a00-0000-1000-8000-00805f9b34fb"
UUID_LIGHT      = "39e1FA01-84a8-11e2-afba-0002a5d5c51b"
UUID_SOIL_EC    = "39e1FA02-84a8-11e2-afba-0002a5d5c51b"
UUID_SOIL_TEMP  = "39e1FA03-84a8-11e2-afba-0002a5d5c51b"
UUID_AIR_TEMP   = "39e1FA04-84a8-11e2-afba-0002a5d5c51b"
UUID_LIVE_NOTIF = "39e1FA06-84a8-11e2-afba-0002a5d5c51b"

HDL_LIVE_NOTIF  = 0x0039
HDL_LED         = 0x003c

HDL_LIGHT_NOTIF     = 0x26
HDL_SOIL_EC_NOTIF   = 0x2A
HDL_SOIL_TEMP_NOTIF = 0x2e
HDL_AIR_TEMP_NOTIF  = 0x32
HDL_SOIL_VWC_NOTIF  = 0x36

HDL_CAL_SOIL_VWC_NOTIF  = 0x44
HDL_CAL_AIR_TEMP_NOTIF  = 0x48
HDL_CAL_DLI_NOTIF       = 0x4c
HDL_CAL_EA_NOTIF        = 0x50
HDL_CAL_ECB_NOTIF       = 0x54
HDL_CAL_EC_POR_NOTIF    = 0x58

HDL_LIGHT     = 0x25
HDL_SOIL_EC   = 0x29
HDL_SOIL_TEMP = 0x2d
HDL_AIR_TEMP  = 0x31
HDL_SOIL_VWC  = 0x35

HDL_CAL_SOIL_VWC = 0x43
HDL_CAL_AIR_TEMP = 0x47
HDL_CAL_DLI      = 0x4b
HDL_CAL_EA       = 0x4f
HDL_CAL_ECB      = 0x53
HDL_CAL_EC_POR   = 0x57

FLAG_NOTIF_ENABLE = "\x01\x00"
FLAG_NOTIF_DISABLE = "\x00\x00"

class CustomRequester(GATTRequester):
    DEF_MULT = 3.3
    DEF_DIV  = 2047 # 2047

    def __init__(self, notif_event, *args):
        GATTRequester.__init__(self, *args)
        self.hevent = notif_event
        self.data = []

    """ 
        Overrrides the on_notification() function of GATTRequester. This will 
         be called whenever a notif we are currently registered to on a BLE
         device is updated with a new value
    """
    def on_notification(self, handle, data):
        if handle == HDL_LIGHT:
            dtype = "Light"
            val = self.conv_light( self.get_charac_value(data) )
        elif handle == HDL_SOIL_EC:
            dtype = "Soil EC"
            #val = (self.get_charac_value(data) * self.DEF_MULT) / self.DEF_DIV
            val = self.conv_ec( self.get_charac_value(data) )
        elif handle == HDL_SOIL_TEMP:
            dtype = "Soil Temp"
            # val = (self.get_charac_value(data) * self.DEF_MULT) / self.DEF_DIV
            val = self.conv_temp( self.get_charac_value(data) )
        elif handle == HDL_AIR_TEMP:
            dtype = "Air Temp"
            # val = (self.get_charac_value(data) * self.DEF_MULT) / self.DEF_DIV
            val = self.conv_temp( self.get_charac_value(data) )
        elif handle == HDL_SOIL_VWC:
            dtype = "Soil VWC"
            # val = (self.get_charac_value(data) * self.DEF_MULT) / self.DEF_DIV
            val = self.conv_moisture( self.get_charac_value(data) )
        elif handle == HDL_CAL_SOIL_VWC:
            dtype = "Soil VSW (cal)"
            val = self.decode_float32(data)
        elif handle == HDL_CAL_AIR_TEMP:
            dtype = "Air Temp (cal)"
            val = self.decode_float32(data)
        elif handle == HDL_CAL_DLI:
            dtype = "DLI (cal)"
            val = self.decode_float32(data)
        elif handle == HDL_CAL_EA:
            dtype = "EA (cal)"
            val = self.decode_float32(data)
        elif handle == HDL_CAL_ECB:
            dtype = "ECB (cal)"
            val = self.decode_float32(data)
        elif handle == HDL_CAL_EC_POR:
            dtype = "EC Porous (cal)"
            val = self.decode_float32(data)
        
        """ Store the value if it is valid """
        if val:
            self.data.append( { "time" : time.time(), "sensor" : dtype, "reading" : round(val,3) } )
            print "%s : %s"  % (dtype, round(val,3))

        self.hevent.set()
        return

    """
        Convenience function for retrieving data from our GATTRequester
    """
    def get_data(self):
        return self.data

    """
        Decodes a 32-bit float from raw/binary data. This is necessary because 
         some of the data retrieved from Parrot Flower Power is in such a 
         format.
    """
    def decode_float32(self, data):
        return struct.unpack('f', data[3:])[0]

    """
        Decodes data from the two byte (uint16) we receive from the Parrot 
         Flower Power.
    """
    def get_charac_value(self, data):
        return  float(struct.unpack('<H', data[3:])[0])

    def conv_temp(self, val):
        dec_val = 0.00000003044 * pow(val, 3.0)
        dec_val -= 0.00008038 * pow(val, 2.0)
        dec_val += 0.1149 * val
        dec_val -= 30.449999999

        if dec_val < -10.0:
            dec_val = -10.0
        elif dec_val > 55.0:
            dec_val = 55.0

        return dec_val

    def conv_ec(self, val):
        if val > 1771:
            return 10.0
        
        dec_val = (val / 1771.0) * 10.0
        return dec_val

    def conv_light(self, val):
        dec_val = 16655.6019 * pow(val, -1.0606619)
        return dec_val

    def conv_moisture(self, val):
        dec_val_tmp = 0.0000000010698 * pow(val, 4.0)
        dec_val_tmp -= 0.00000152538 * pow(val, 3.0)
        dec_val_tmp += 0.000866976 * pow(val, 2.0)
        dec_val_tmp -= 0.169422 * val
        dec_val_tmp += 11.4293

        dec_val = 0.0000045 * pow(dec_val_tmp, 3.0)
        dec_val -= 0.00055 * pow(dec_val_tmp, 2.0)
        dec_val += 0.0292 * dec_val_tmp
        dec_val -= 0.053
        dec_val *= 100.0

        if dec_val < 0.0:
            dec_val = 0.0
        elif dec_val > 60.0:
            dec_val = 60.0

        return dec_val

class Parrot():
    def __init__(self, address):
        self.hevent = Event()
        self.req = CustomRequester(self.hevent, address, False)
        self.ble_char_tbl = [
            [ "Live Notif",             HDL_LIVE_NOTIF,         '\x01'],
            [ "Light Notif",            HDL_LIGHT_NOTIF,        FLAG_NOTIF_ENABLE],
            [ "Soil Temp Notif",        HDL_SOIL_TEMP_NOTIF,    FLAG_NOTIF_ENABLE]
        ]

        self.ble_char_old_tbl = [
            [ "Air Temp Notif",        HDL_AIR_TEMP_NOTIF,    FLAG_NOTIF_ENABLE],
            [ "Soil VWC Notif",        HDL_SOIL_VWC_NOTIF,    FLAG_NOTIF_ENABLE],
            [ "Soil EC Notif",         HDL_SOIL_EC_NOTIF,    FLAG_NOTIF_ENABLE]
        ]

        self.ble_char_new_tbl = [
            [ "Calib EA Notif",         HDL_CAL_EA_NOTIF,       FLAG_NOTIF_ENABLE],
            [ "Calib Air Temp Notif",   HDL_CAL_AIR_TEMP_NOTIF, FLAG_NOTIF_ENABLE],
            [ "Calib Soil VWC Notif",   HDL_CAL_SOIL_VWC_NOTIF, FLAG_NOTIF_ENABLE],
            [ "Calib DLI Notif",        HDL_CAL_DLI_NOTIF,      FLAG_NOTIF_ENABLE],
            [ "Calib ECB Notif",        HDL_CAL_ECB_NOTIF,      FLAG_NOTIF_ENABLE],
            [ "Calib EC Porous Notif",  HDL_CAL_EC_POR_NOTIF,   FLAG_NOTIF_ENABLE]
        ]

    def get_event_hdl(self):
        return self.hevent

    def start(self):
        """ Connect using the GATTRequester """
        self.req.connect(True)

        # TODO Check if the connection is available first !

        print "Starting live measurements..."
        """
            For each element in the BLE Characteristic table, write the 
            activation parameter (pset[2]) for each BLE characteristic
            handle (pset[1]). The first field (pset[0]) is just a string
            identifier.
        """
        for pset in self.ble_char_tbl:
            try:
                self.req.write_by_handle(pset[1], pset[2])
            except:
                e = sys.exc_info()[0]
                print e
                print ("{}: FAILED".format(pset[0]))
                return False
            print ("{}: OK".format(pset[0]))

        is_firmware_new = True
        for pset in self.ble_char_new_tbl:
            try:
                self.req.write_by_handle(pset[1], pset[2])
            except:
                e = sys.exc_info()[0]
                print e
                print ("{}: FAILED".format(pset[0]))
                # return False
                is_firmware_new = False
                break
                
            print ("{}: OK".format(pset[0]))

        if is_firmware_new:
            return True

        print "Warning: Device might have older Parrot Flower Power firmware"
        for pset in self.ble_char_old_tbl:
            try:
                self.req.write_by_handle(pset[1], pset[2])
            except:
                e = sys.exc_info()[0]
                print e
                print ("{}: FAILED".format(pset[0]))
                return False
            print ("{}: OK".format(pset[0]))
       
        return True

    def get_name(self):
        # TODO Check if the connection is available first !
        data = self.req.read_by_uuid(UUID_NAME)[0]
        name = "[UNKNOWN]"

        try:
            name = data.decode("utf-8")
        except AttributeError:
            name = "[UNKNOWN]"

        return name

    def trigger_led(self, activate=True):
        # TODO Check if the connection is available first !
        if activate:
            self.req.write_by_handle(HDL_LED, '\x01')
            return True

        self.req.write_by_handle(HDL_LED, '\x00')
        return True

    def stop(self):
Parrot        # TODO Check if the connection is available first !
        self.req.write_by_handle(HDL_LIVE_NOTIF, '\x00')
        self.req.disconnect()
        return True

    def get_data(self):
        return self.req.get_data()

