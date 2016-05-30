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
        print "Notif received: {}, {}".format(handle, data)
        self.hevent.set()
        return

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

        print "Model No: {}".format(model_no)

        print "Attempting to write to Command Characteristic..."
        self.req.write_by_handle(HDL_COMMAND, DFR_PWD_STR)
        self.req.write_by_handle(HDL_COMMAND, DFR_BDR_STR)
        
        self.req.write_by_handle(HDL_SERIAL, FLAG_NOTIF_ENABLE)

        return True

    def request(self, request):
        req_str = str(bytearray(request))
        print req_str
        self.req.write_by_handle(HDL_SERIAL, req_str)
        return True

    def stop(self):
        self.req.disconnect()
        return

# bluno_test = Bluno("C4:BE:84:28:89:4A")
# handle_event = bluno_test.get_event_hdl()
# bluno_test.start()
# 
# time.sleep(3)
# 
# bluno_test.request(b"READ;\r\n")
# counter = 10
# while counter > 0:
#     handle_event.wait(5)
#     counter -= 1
#     handle_event.clear()
#     print "Counts left:", counter
#     if ((10-counter) % 3) == 0:
#         bluno_test.request(b"READ;\r\n")
# 
# bluno_test.stop()

