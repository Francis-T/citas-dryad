from dryad.database import DryadDatabase
from dryad_mt.request_handler import RequestHandler
from random import random
import json
import pprint

FLAG_SETUP_DB = True
FLAG_ADD_NODES = False
FLAG_ADD_DATA = True

def gen_data():
    data = {}
    data['pH'] = 14.00 * random()
    data['EC'] = 1450000.0 * random()
    data['temp'] = 100 * random()
    data['origin'] = { "name" : "A", "lat": 14, "lon": 120, "addr":"!@#!@#!@#!@#!@" }
    return data


## Main Program ##
if FLAG_SETUP_DB == True:
    ddb = DryadDatabase()
    ddb.connect("test.db")
    ddb.setup()

    if FLAG_ADD_NODES:
        ddb.add_node("SN01", "SENSOR")
        ddb.add_node("SN02", "SENSOR")
        ddb.add_node("CN01", "CACHE")
        ddb.add_node_device("11:22:33:44:55:66", "SN01", "PARROT_FP")
        ddb.add_node_device("44:22:33:11:55:66", "SN01", "BLUNO_BT")
        ddb.add_node_device("55:22:33:44:55:66", "SN02", "PARROT_FP")
        ddb.add_node_device("22:22:33:11:55:66", "SN02", "BLUNO_BT")
        ddb.add_node_device("55:33:33:44:55:66", "CN01", "RPI_3")

    ddb.start_capture_session()
    curr_session = ddb.get_current_session()
    print("Current session = {}".format(str(curr_session)))

    if FLAG_ADD_DATA:
        # ts = 47
        # src = "SN3"
        # data = {}
        ddb.add_data(session_id=curr_session, source="SN01", content=json.dumps(gen_data()), dest="CN01")
        ddb.add_data(session_id=curr_session, source="SN01", content=json.dumps(gen_data()), dest="CN01")
        ddb.add_data(session_id=curr_session, source="SN01", content=json.dumps(gen_data()), dest="CN01")
        ddb.add_data(session_id=curr_session, source="SN02", content=json.dumps(gen_data()), dest="CN01")
        ddb.add_data(session_id=curr_session, source="SN02", content=json.dumps(gen_data()), dest="CN01")
        ddb.add_data(session_id=curr_session, source="SN02", content=json.dumps(gen_data()), dest="CN01")

    ddb.end_capture_session()
    print("Current session = {}".format(str(ddb.get_current_session())))
    
    ddb.disconnect()

# print(str(ddb.get_data()))

rqh = RequestHandler(None, None, None, "test.db")

rqh.handle_req_download(None, "")


# pprint.pprint( ddb.get_compressed_data() )
# ddb.disconnect()


