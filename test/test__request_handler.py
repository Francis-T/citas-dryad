"""
    Name:   test__request_handler.py
    Author: Francis T
    Desc:   Source code for testing the Request Handler
"""

import os

from threading import Event
from queue import Queue

from dryad.node_state import NodeState
from dryad.database import DryadDatabase
from dryad.request_handler import RequestHandler

SYS_CMD_BNAME = "hciconfig hci0 name | grep \"Name\" | sed -r \"s/\s+Name: '(.+)'/\\1/g\""
SYS_CMD_ADDR = "hciconfig hci0 name | grep \"BD Address\" | sed -r \"s/\s+BD Address: (.+)  ACL.+/\\1/g\"" 

CLASS = "CACHE"
TYPE = "SELF"

class TestSuite():
    def __init__(self):
        self.link = None
        self.reqh = None
        self.event = None
        self.queue = None
        self.state = None
        return

    def setup(self):
        db_name = "test.db"
        version = "1.1"

        self.link = DummyLink()
        self.event = Event()
        self.queue = Queue()

        self.state = NodeState()
        self.state.set_state("UNKNOWN")

        dcn = DummyCacheNode(db_name)
        dcn.setup_database()
        dcn.simulate_sampling()

        self.reqh = RequestHandler(self.event, 
                                   self.queue, 
                                   self.state, 
                                   db_name, 
                                   version)
        return

    def teardown(self):
        return

    def run(self):
        self.setup()

        test_inputs = [
           "QCUPD:name='francis.t',lat=14.37,lon=120.58,site_name='CITAS-Ateneo';",
           "QACTV:;",
           "QSTAT:;",
           "QQRSN:name='SN77',pf_addr='001122334455',bl_addr='55AA33221100',state='AOK',lat=14.37,lon=120.58,updated=123213124;",
           "QQRSN:name='SN78',pf_addr='007777777777',bl_addr='777733221100',state='AOK',lat=14.37,lon=120.58,updated=123213124;",
           "QNLST:;",
           "QSUPD:name='SN78',site_name=\"CITAS\",state='NOK',lat=14.37,lon=120.58;",
           "QNLST:;",
           "QDLTE:rpi_name='LEGO',sn_name='SN77';",
           "QNLST:;",
           "QDLTE:rpi_name='LEGO',sn_name='SN78';",
           "QNLST:;",
           "QQRSN:name='SN77',pf_addr='001122334455',bl_addr='55AA33221100',state='AOK',lat=14.37,lon=120.58,updated=123213124;",
           "QQRSN:name='SN78',pf_addr='007777777777',bl_addr='777733221100',state='AOK',lat=14.37,lon=120.58,updated=123213124;",
           "QNLST:;",
           "QDATA:;",
           "QDEAC:;",
           "QPWDN:;"
        ]

        # Execute tests
        for test_inp in test_inputs:
            print("=======================================================")
            print(">  Input: {}".format(test_inp))
            result = self.reqh.handle_request(self.link, test_inp)
            if (result == False):
                print(">  Test Failed")
                continue
            print(">  Test OK")

        self.teardown()
        return


class DummyCacheNode():
    def __init__(self, db_name):
        self.db_name = db_name
        return

    def setup_database(self):
        ddb = DryadDatabase()
        if ddb.connect(self.db_name) == False:
            print("Failed to connect to database")
            return False

        # Setup the database if necessary
        if ddb.setup() == False:
            print("Failed to setup database")
            return False
        
        self_name = os.popen(SYS_CMD_BNAME).read().split(' ')[0].strip()
        self_address = os.popen(SYS_CMD_ADDR).read().strip()

        self_node = ddb.get_nodes(condition="td.c_type = 'SELF'")
        if (self_node == None or len(self_node) <= 0):
            ddb.add_node(node_id=self_name, node_class=CLASS)
            ddb.add_node_device(node_addr=self_address, node_id = self_name, node_type = TYPE)

        print("Added cache node details")
        ddb.disconnect()
        return True

    def simulate_sampling(self):
        return True


class DummyLink():
    def __init__(self):
        self.data_list = []
        self.connected = False
        return

    def init_socket(self, timeout=180.0):
        #print("DummyLink.init_socket() called.")
        return True

    def is_connected(self):
        return self.connected

    def listen(self):
        #print("DummyLink.listen() called.")
        self.connected = True
        return True

    def add_data(self, data):
        self.data_list.append(data)
        return True

    def receive_data(self):
        #print("DummyLink.receive_data() called.")
        data = self.data_list[0]
        del self.data_list[0]
        print(">  Data received [   {}   ]".format(data))

        return data

    def send_response(self, resp_data):
        #print("DummyLink.send_response() called.")
        #print("Sending response...")
        print(">  Sent Response [   {}   ]".format(resp_data.strip()))
        return True

    def disconnect(self):
        #print("DummyLink.disconnect() called.")
        return True

    def destroy(self):
        #print("DummyLink.destroy() called.")
        return

