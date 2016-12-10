"""
    Name: request_handler.py
    Author: Francis T
    Desc: Source code for the Cache Node request handler
"""
import logging
import json
import pprint as pp

from queue import Queue
from threading import Event

from dryad.database import DryadDatabase
from dryad_mt.node_state import NodeState

CLASS_SENSOR = "SENSOR"

TYPE_PARROT = "PARROT"
TYPE_BLUNO = "BLUNO"

class RequestHandler():
    def __init__(self, event, queue, state, db_name, version):
        self.hevent = event
        self.queue = queue
        self.nstate = state
        self.dbname = db_name
        self.version = version
        
        self.logger = logging.getLogger("main.RequestHandler")
        return

    def handle_req_state(self, link, content):
        db = DryadDatabase()
        if db.connect(self.dbname) == False:
            return False
    
        # Retrive details about the cache node from the database
        details = db.get_self_details()    

        # Format the string to return
        state = "'state':'{}','batt':{},'version':'{}','lat':{},'lon':{}"
        state = state.format(self.nstate.get_state(), details[3], self.version, details[1], details[2])
        
        return link.send_response("RSTAT:{" + state + "};\r\n")

    def handle_req_activate(self, link, content):
        # Add an activation request to the main cache node queue
        self.queue.put("ACTIVATE")

        # And trigger the event handler
        self.hevent.set()

        return link.send_response("RACTV:OK;\r\n")

    def handle_req_deactivate(self, link, content):
        # Add a deactivation request to the main cache node queue
        self.queue.put("DEACTIVATE")

        # And trigger the event handler
        self.hevent.set()

        return link.send_response("RDEAC:OK;\r\n")

    def handle_req_update_cache(self, link, content):
        params = {"name":None, "lat":None, "lon":None}

        # remove trailing ";" 
        if ";" in content:
            content = content[:-1]

        update_args = content.split(',')
        
        if len(update_args) > 0:
            for arg in update_args:
                if "=" in arg:
                    param = arg.split("=")[0]
                    val = arg.split("=")[1]
                    try:
                        val = float(val)
                    except:
                        pass
                    if param in params.keys():
                        params[param] = val     
        db = DryadDatabase()
        if db.connect(self.dbname) == False:
            return False

        db.update_self_details(params["name"], params["lat"], params["lon"])
        return link.send_response("RCUPD:OK;\r\n")

    def handle_req_list_sensors(self, link, content):
        # TODO Retrieve sensors list from db
        db = DryadDatabase()
        if db.connect(self.dbname) == False:
            return False
        nodes = db.get_nodes("tn.c_class = 'SENSOR'")

        if sensors is None:
            sensors = ""

		 
        #sensors = "{'sensor_id': [{'id': 'xx-123', 'name': 'sn1', 'state': 'pending deployment', 'date_updated': '12-10-94', 'site_name': 'Maribulan', 'lat': '10.12', 'lon': '123.12', 'pf_batt': '98', 'bl_batt': '80'}, {'id': 'xx-124', 'name': 'sn2', 'state': 'deployed', 'date_updated': '12-10-95', 'site_name': 'Maribulan', 'lat': '10.12', 'lon': '125.12', 'pf_batt': '70', 'bl_batt': '80'}]}"
        
        return link.send_response("RNLST:" + sensors + ";\r\n")
   
    def handle_req_setup_sensor(self, link, content):
        # TODO Add new sensor node settings
        params = {
            "name"        : None, 
            "pf_addr"    : None, 
            "bl_addr"    : None,
            "state"        : None,
            "lat"        : None,
            "lon"        : None, 
            "updated"    : None,
        }

        # remove trailing ";" 
        if ";" in content:
            content = content[:-1]
        else:
            return False # Incomplete content

        update_args = content.split(',')
        
        if len(update_args) > 0:
            for arg in update_args:
                if "=" in arg:
                    param = arg.split("=")[0]
                    val = arg.split("=")[1]
                    try:
                        val = float(val)
                    except:
                        pass
                    if param in params.keys():
                        params[param] = val     
        db = DryadDatabase()
        if db.connect(self.dbname) == False:
            return False

        # TODO Ask if we can have lat lon placed in node rather than node_device
        db.add_node(node_name=params["name"], node_class=CLASS_SENSOR)
        db.add_node_device(node_addr=params["bl_addr"], node_name=params["name"], node_type=TYPE_BLUNO, lat=params["lat"], lon=params["lon"])
        db.add_node_device(node_addr=params["pf_addr"], node_name=params["name"], node_type=TYPE_PARROT, lat=params["lat"], lon=params["lon"])
        
        return link.send_response("RQRSN:OK;\r\n")

    def handle_req_update_sensor(self, link, content):
        # TODO Update sensor details in the database
        return link.send_response("RSUPD:OK;\r\n")

    def handle_req_remove_sensor(self, link, content):
        # TODO Update sensor details in the database
        return link.send_response("RDLTE:OK;\r\n")

    def handle_req_shutdown(self, link, content):
        # Add a deactivation request to the main cache node queue
        self.queue.put("SHUTDOWN")

        # And trigger the event handler
        self.hevent.set()

        return link.send_response("RPWDN:OK;\r\n")
        
    def handle_req_download(self, link, content):
        limit = None
        start_id = None
        end_id = None
        unsent_only = False

        download_args = content.split(',')

        # Parse our argument list
        if len(download_args) > 0:
            for arg in download_args:
                # TODO This part needs to be cleaned up

                if arg.lower().startswith("limit="):
                    limit = int(arg.split('=')[1])

                elif arg.lower().startswith("start_id="):
                    # TODO Not yet used!
                    start_id = int(arg.split('=')[1])

                elif arg.lower().startswith("end_id="):
                    # TODO Not yet used!
                    end_id = int(arg.split('=')[1])

                elif arg.lower().startswith("unsent_only="):
                    # TODO Not yet used!
                    val = arg.split('=')[1]
                    if val == "True":
                        unsent_only = True
                    else:
                        unsent_only = False

        db = DryadDatabase()
        if db.connect(self.dbname) == False:
            return False

        if limit == None:
            limit = 5

        records = db.get_data(limit=limit, summarize=False)
        while records != None:
            proc_ids = []
            resp_data = []

            # Compose our response content
            for rec in records:
                proc_ids.append( rec[0] )

                resp_data.append( {
                    "data" : json.loads("[" + rec[3] + "]"),
                    "timestamp" : rec[2],
                    "sampling_site" : "Ateneo"
                } )
            
            # Send our response
            try:
                resp = json.dumps(resp_data)
                # pp.pprint(resp_data)
                if link.send_response(resp) == False:
                    self.logger.error("Failed to send response")
                    db.disconnect()
                    return False
            except:
                self.logger.error("Failed to send response due to an exception")
                db.disconnect()
                return False
            
            # Once data is sent successfully, we can mark off the records whose
            #   IDs we took note of earlier in our database
            #for rec_id in proc_ids:
            #    db.set_data_uploaded(rec_id)

            # Get a new batch of unsent records
            records = db.get_data(50)
            
            if len(records) < 1:
                self.logger.info("No more data to send")
                break

            break

        db.disconnect()

        return True

    def handle_request(self, link, request):
        # self.logger.info("Message received: {}".format(msg))

        req_parts = request.split(':', 2)

        if not len(req_parts) == 2:
            self.logger.error("Malformed request: {}".format(request))
            return False

        req_hdr = req_parts[0]
        req_content = req_parts[1].strip(';').strip()

        if req_hdr == "QSTAT":
            # State request
            if self.handle_req_state(link, req_content) == False:
                self.logger.error("Failed to handle {} request".format(req_hdr))
                return False

        elif req_hdr == "QACTV":
            # Activate Cache Node request
            if self.handle_req_activate(link, req_content) == False:
                self.logger.error("Failed to handle {} request".format(req_hdr))
                return False

        elif req_hdr == "QDEAC":
            # Deactivate Cache Node request
            if self.handle_req_deactivate(link, req_content) == False:
                self.logger.error("Failed to handle {} request".format(req_hdr))
                return False

        elif req_hdr == "QCUPD":
            # Update cache details
            if self.handle_req_update_cache(link, req_content) == False:
                self.logger.error("Failed to handle {} request".format(req_hdr))
                return False

        elif req_hdr == "QNLST":
            # Display sensor nodes list
             if self.handle_req_list_sensors(link, req_content) == False:
                self.logger.error("Failed to handle {} request".format(req_hdr))
                return False

        elif req_hdr == "QQRSN":
            # Add new sensor node from QR code
             if self.handle_req_setup_sensor(link, req_content) == False:
                self.logger.error("Failed to handle {} request".format(req_hdr))
                return False

        elif req_hdr == "QSUPD":
            # Update sensor details
             if self.handle_req_update_sensor(link, req_content) == False:
                self.logger.error("Failed to handle {} request".format(req_hdr))
                return False
      
        elif req_hdr == "QDLTE":
            # Update sensor details
             if self.handle_req_remove_sensor(link, req_content) == False:
                self.logger.error("Failed to handle {} request".format(req_hdr))
                return False
      
 
        elif req_hdr == "QPWDN":
            # Shutdown Program request (undocumented feature)
            if self.handle_req_shutdown(link, req_content) == False:
                self.logger.error("Failed to handle {} request".format(req_hdr))
                return False

        elif req_hdr == "QDATA":
            # Download Data request
            if self.handle_req_download(link, req_content) == False:
                self.logger.error("Failed to handle {} request".format(req_hdr))
                return False

        return True

