"""
    Name: mobile_bt.py
    Author: Francis T
    Description:
        Source code for the Mobile Node Bluetooth link controller
"""
import socket
import json

HOST = ''                 # The remote host
PORT = 50007              # The same port as used by the server

class FlaskLink():
    def __init__(self):
        self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client_sock = None
        self.connected = False
        return

    def init_socket(self, timeout=180.0):
        self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # Bind socket to a port and listen
        self.server_sock.bind((HOST, PORT))

        # Configure the socket to listening mode
        self.server_sock.listen(5)

        # Configure timeout for incoming connections (default: 180 secs)
        self.server_sock.settimeout(timeout)
        return True

    def is_connected(self):
        return self.connected

    def listen(self):
        try:
            self.client_sock, client_info = self.server_sock.accept()
        except Exception as e:
            print("Exception occurred at listen: " + str(e))
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
        except Exception as e:
            print("Exception occured during receive: " + str(e))
            self.connected = False
            return None

        if not data:
            return None

        if data == b'':
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
            self.client_sock.sendall(resp_data.encode('UTF-8'))
        except Exception as e:
            print("Send failed: {}".format(str(e)))
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


