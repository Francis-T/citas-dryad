"""
    Name: bluno_ble.py
    Author: Francis T
    Description:
        Source code for the Bluno BLE controller
"""
import time
from threading import Event
from bluetooth.ble import GATTRequester

""" Constants """
UUID_SERIAL     = "0000dfb1-0000-1000-8000-00805F9B34FB"
UUID_COMMAND    = "0000dfb2-0000-1000-8000-00805F9B34FB"
UUID_MODEL_NO   = "00002a24-0000-1000-8000-00805F9B34FB"
UUID_NAME       = "00002a00-0000-1000-8000-00805f9b34fb"

HDL_SERIAL  = 0x0025
HDL_COMMAND = 0x0028

FLAG_NOTIF_ENABLE = "\x01\x00"
FLAG_NOTIF_DISABLE = "\x00\x00"

DFR_PWD_STR = str(bytearray(b"AT+PASSWOR=DFRobot\r\n"))
DFR_BDR_STR = str(bytearray(b"AT+CURRUART=115200\r\n"))

class CustomRequester(GATTRequester):
    def __init__(self, notif_event, *args):
        GATTRequester.__init__(self, *args)
        self.hevent = notif_event
        self.data = []
    
    def on_notification(self, handle, data):
        # If the data is of interest to us, save it
        if "pH" in data:
            dtype = "pH"
            val = float( data.strip().split(": ", 1)[1] )
        
            self.data.append( { "time" : time.time(), "sensor" : dtype, "reading" : round(val,3) } )
            print("%s : %s"  % (dtype, round(val,3)))
            
        self.hevent.set()
        return

    def get_data(self):
        return self.data

class Bluno():
    def __init__(self, address):
        self.hevent = Event()
        self.req = CustomRequester(self.hevent, address, False)

    def get_event_hdl(self):
        return self.hevent

    def start(self):
        """ Connect using the GATTRequester """
        self.req.connect(True)
        """ Try to pull the model number to see if this really is a Bluno """
        try:
            model_no = self.req.read_by_uuid(UUID_MODEL_NO)
        except:
            return False

        print("Model No: {}".format(model_no))
        
        self.req.write_by_handle(HDL_SERIAL, FLAG_NOTIF_ENABLE)
        
        print("Starting read...")
        self.start_read()

        return True

    def check(self):
        return self.request("check")

    def start_read(self):
        return self.request("read.start")

    def stop_read(self):
        return self.request("read.stop")

    def request(self, request):
        req_str = str(bytearray(request))
        print(req_str)
        self.req.write_by_handle(HDL_SERIAL, req_str)
        return True

    def get_name(self):
        name = "[UNKNOWN]"

        # Check if the connection is available first !
        if not self.req.is_connected():
            print("Not Connected")
            return name

        data = self.req.read_by_uuid(UUID_NAME)[0]
        try:
            name = data.decode("utf-8")
        except AttributeError:
            name = "[UNKNOWN]"

        return name

    def stop(self):
        self.stop_read()
        self.req.disconnect()
        return

    def get_data(self):
        return self.req.get_data()

