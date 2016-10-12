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
        self.connected = False
        return

    def init_socket(self, timeout=180.0):
        # Bind socket to a port and listen
        self.server_sock.bind(("", PORT_ANY))

        # Configure the socket to listening mode
        self.server_sock.listen(1)

        # Configure timeout for incoming connections (default: 180 secs)
        self.server_sock.settimeout(timeout)
        return True

    def is_connected(self):
        return self.connected

    def listen(self):
        try:
            self.client_sock, client_info = self.server_sock.accept()
        except BluetoothError:
            return False

        if client_info == None:
            return False

        print("Connection accepted from " + str(client_info))
        self.connected = True
        return True

    def receive_data(self):
        if self.connected == False:
            print("Not connected")
            return False

        if self.client_sock == None:
            print("No clients to receive data from")
            return None

        try:
            data = self.client_sock.recv(2056)
        except BluetoothError:
            self.connected = False
            return None

        if data == None:
            return None

        print("Data received [%s]" % data)

        return data

    def send_response(self, resp_data):
        if self.connected == False:
            print("Not connected")
            return False

        if self.client_sock == None:
            print("No clients to respond to")
            return False

        print("Sending response...")
        try:
            self.client_sock.send(resp_data)
        except BluetoothError:
            self.connected = False
            return False

        print("RESPONSE [%s]" % resp_data)

        return True

    def disconnect(self):
        if self.client_sock == None:
            print("No clients to disconnect from")
            return False

        self.client_sock.close()
        self.connected = False
        return True

    def destroy(self):
        self.server_sock.close()
        self.connected = False
        return


