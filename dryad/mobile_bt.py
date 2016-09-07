"""
    Name: mobile_bt.py
    Author: Francis T
    Description:
        Source code for the Mobile Node Bluetooth link controller
"""
from bluetooth import *
import json

class MobileNode():
    def __init__(self):
        self.server_sock = BluetoothSocket(RFCOMM)
        self.client_sock = None

    def init_socket(self, timeout=180.0):
        # Bind socket to a port and listen
        self.server_sock.bind(("", PORT_ANY))

        # Configure the socket to listening mode
        self.server_sock.listen(1)

        # Configure timeout for incoming connections (default: 180 secs)
        self.server_sock.settimeout(timeout)
        return True

    def listen(self):
        print("Awaiting connections...")
        try:
            self.client_sock, client_info = self.server_sock.accept()
        except BluetoothError:
            print("No connections found")
            return False

        print("Connection accepted from", client_info)
        return True

    def receive_data(self):
        if self.client_sock == None:
            print("No clients to receive data from")
            return None

        data = ""
        try:
            while True:
                temp_data = self.client_sock.recv(2056)
                if len(temp_data) == 0:
                    break
                if len(temp_data) < 2056:
                    data += temp_data
                    break
                data += temp_data
            print("Data received [%s]" % data)
        except IOError:
            print("Failed to receive data")
            return None

        return data

    def send_response(self, resp_data):
        if self.client_sock == None:
            print("No clients to respond to")
            return False

        print("Sending response...")
        self.client_sock.send(json.dumps(resp_data))
        print("RESPONSE [%s]" % json.dumps(resp_data))

        return True

    def disconnect(self):
        if self.client_sock == None:
            print("No clients to disconnect from")
            return False

        self.client_sock.close()
        return True

    def destroy(self):
        self.server_sock.close()


