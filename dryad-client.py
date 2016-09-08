import sys
import time
from bluetooth import *

class DryadClient:
    def __init__(self):
        self.server_sock = None
        return

    def run(self, bdaddr, port):
        sock = BluetoothSocket( RFCOMM )
        sock.connect((bdaddr, port))

        print "Sending data..."
        sock.send("hello python111");

        print "Receiving response..."
        data = ""
        seg_len = 2056
        is_seg_len_set = False
        while True:
            temp_data = sock.recv(seg_len)
            data += temp_data

            if (len(temp_data) != seg_len) and (is_seg_len_set == False):
                seg_len = len(temp_data)
                is_seg_len_set = True
                continue

            if len(temp_data) == 0:
                break
            if len(temp_data) < seg_len:
                break
        print "Data received [%s]" % data

        time.sleep(2.5)

        sock.close()

        return

dc = DryadClient()
dc.run("00:1A:7D:DA:71:11", 1)

