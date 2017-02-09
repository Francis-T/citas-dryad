"""
    Name: request_handler.py
    Author: Jerelyn C / Francis T
    Desc: Source code for the Cache Node request handler
"""
import logging
import json
import pprint as pp

from time import time
from queue import Queue
from threading import Event

from utils.transform import DataTransformation
from dryad.database import DryadDatabase
from dryad.node_state import NodeState

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

        # Disconnect from the DB since we no longer need it
        db.disconnect()

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

    def handle_req_add_collection_params(self, link, content):
        # remove trailing ";" 
        if ";" in content:
            content = content[:-1]

        params_args = content.split(',')

        # Parse our argument list
        if len(params_args) > 0:
            for arg in params_args:
                if arg.lower().startswith("duration="):
                    duration = int(arg.split('=')[1])

                elif arg.lower().startswith("interval="):
                    interval = int(arg.split('=')[1])

                elif arg.lower().startswith("max_samples="):
                    max_samples = int(arg.split('=')[1])
        
            db = DryadDatabase()
            if db.connect(self.dbname) == False:
                return False
            
            result = db.add_collection_parameters(duration, interval, max_samples)

            if result == False:
                self.logger.error("Failed to add_collection_parameters")
                link.send_response("QASCP:FAIL;\r\n")
                return False
            
        # Add an activation request to the main cache node queue
        self.queue.put("SET_PARAMS")

        # And trigger the event handler
        self.hevent.set()

        
        return link.send_response("RASCP:OK;\r\n")

    def handle_req_update_cache(self, link, content):
        params = {
            "name"      :   None, 
            "lat"       :   None, 
            "lon"       :   None, 
            "site_name" :   None
        }

        # remove trailing ";" 
        if ";" in content:
            content = content[:-1]

        update_args = content.split(',')
        
        if len(update_args) > 0:
            for arg in update_args:
                if "=" in arg:
                    param = arg.split("=")[0]
                    val = arg.split("=")[1]

                    if param in params.keys():
                        if param == "lat" or param == "lon":
                            val = float(val)
                            params[param] = val
                        else:
                            params[param] = val.strip("'").strip('"')

        db = DryadDatabase()
        if db.connect(self.dbname) == False:
            return False

        # Update cache node details in the DB
        result = db.update_self_details(node_id = params["name"], 
                                        lat = params["lat"], 
                                        lon = params["lon"],
                                        site_name = params["site_name"])
        if result == False:
            self.logger.error("Failed to update cache node details")
            link.send_response("RCUPD:FAIL;\r\n")
            return False

        # Disconnect from the DB since we no longer need it
        db.disconnect()

        return link.send_response("RCUPD:OK;\r\n")

    def handle_req_list_sensors(self, link, content):
        db = DryadDatabase()
        if db.connect(self.dbname) == False:
            return False
        nodes = db.get_nodes("tn.c_class = 'SENSOR'")
        
        # print(nodes)
        sensors = "" 
        if len(nodes) > 0:
            sensors += "{'sensors':["
            for idx in range(int(len(nodes)/2)):
                sn = "'name':'{}', 'state':'{}',"
                sn += "'site_name':'{}','lat':'{}', 'lon':'{}',"
                sn += "'pf_addr':'{}', 'bl_addr':'{}', 'pf_batt':'{}',"
                sn += "'bl_batt':'{}'"

                
                # Add state in node devices table
                # By Pair access of sensor nodes details. Brute force.Should be in sql query
                sn = sn.format(nodes[2*idx][1], nodes[2*idx][10], nodes[2*idx][6], nodes[2*idx][3], nodes[2*idx][4], nodes[2*idx+1][0], nodes[2*idx][0], nodes[2*idx+1][5], nodes[2*idx][5])
 
                # If last entry, no comma
                if idx is (int(len(nodes)/2))-1:
                    sn = "{" + sn + "}"
                else:                
                    sn = "{" + sn + "},"
                sensors += sn
            sensors += "]}"
        else:
            sensors = "" 
   
        # print(sensors)
         
        return link.send_response("RNLST:" + sensors + ";\r\n")
   
    def handle_req_setup_sensor(self, link, content):
        params = {
            "name"        : None, 
            "pf_addr"    : None, 
            "bl_addr"   : None,
            "state"     : None,
            "lat"       : None,
            "lon"       : None, 
            "updated"   : None,
        }

        # remove trailing ";" 
        if ";" in content:
            content = content[:-1]

        update_args = content.split(',')
        
        if len(update_args) > 0:
            for arg in update_args:
                if "=" in arg:
                    param = arg.split("=")[0]
                    val = arg.split("=")[1]

                    if param in params.keys():
                        if param == "lat" or param == "lon":
                            val = float(val)
                            params[param] = val
                        else:
                            params[param] = val.strip("'").strip('"')

        db = DryadDatabase()
        if db.connect(self.dbname) == False:
            return False

        dt = DataTransformation()
        bl_addr = dt.conv_mac(params["bl_addr"].upper())
        pf_addr = dt.conv_mac(params["pf_addr"].upper())

        result = db.add_node(node_id=params["name"], node_class=CLASS_SENSOR)
        if result == False:
            self.logger.error("Failed to add node")
            link.send_response("RQRSN:FAIL;\r\n")
            return False

        result = db.add_node_device(node_addr=bl_addr, node_id=params["name"], node_type=TYPE_BLUNO, lat=params["lat"], lon=params["lon"], last_updated=time())
        if result == False:
            self.logger.error("Failed to add node device")
            link.send_response("RQRSN:FAIL;\r\n")
            return False

        result = db.add_node_device(node_addr=pf_addr, node_id=params["name"], node_type=TYPE_PARROT, lat=params["lat"], lon=params["lon"], last_updated=time())
        if result == False:
            self.logger.error("Failed to add node device")
            link.send_response("RQRSN:FAIL;\r\n")
            return False
        
        return link.send_response("RQRSN:OK;\r\n")

    def handle_req_update_sensor(self, link, content):
        params = {
            "name"        : None, 
            "site_name"    : None, 
            "state"        : None,
            "lat"       : None,
            "lon"       : None, 
        }

        # remove trailing ";" 
        if ";" in content:
            content = content[:-1]

        update_args = content.split(',')
        
        if len(update_args) > 0:
            for arg in update_args:
                if "=" in arg:
                    param = arg.split("=")[0]
                    val = arg.split("=")[1]

                    if param in params.keys():
                        if param == "lat" or param == "lon":
                            val = float(val)
                            params[param] = val
                        else:
                            params[param] = val.strip("'").strip('"')

        db = DryadDatabase()
        if db.connect(self.dbname) == False:
            return False

        result = db.update_node(node_id=params["name"], site_name=params["site_name"])
        if result == False:
            self.logger.error("Failed to update node")
            link.send_response("RSUPD:FAIL;\r\n")
            return False

        result = db.update_node_device(node_id=params["name"], lat=params["lat"], lon=params["lon"], updated=time())
        if result == False:
            self.logger.error("Failed to update node device")
            link.send_response("RSUPD:FAIL;\r\n")
            return False

        return link.send_response("RSUPD:OK;\r\n")

    def handle_req_remove_sensor(self, link, content):
        params = {
            "rpi_name"    : None, 
            "sn_name"   : None, 
        }

        remove_args = content.split(',')
        
        if len(remove_args) > 0:
            for arg in remove_args:
                if "=" in arg:
                    param = arg.split("=")[0]
                    val = arg.split("=")[1]

                    if param in params.keys():
                        if param == "lat" or param == "lon":
                            val = float(val)
                            params[param] = val
                        else:
                            params[param] = val.strip("'").strip('"')
       
        db = DryadDatabase()
        if db.connect(self.dbname) == False:
            return False

        result = db.remove_node(node_id=params["sn_name"], node_class="SENSOR")
        if result == False:
            self.logger.error("Failed to remove node")
            link.send_response("RDLTE:FAIL;\r\n")
            return False

        result = db.remove_node(node_id=params["sn_name"], node_class="SELF" ) 
        if result == False:
            self.logger.error("Failed to remove node")
            link.send_response("RDLTE:FAIL;\r\n")
            return False

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

        # Indices
        idx = {
            "id"            : 0,
            "source"        : 1,
            "end_time"      : 2,
            "dest"          : 3,
            "ph"            : 4,
            "sunlight"      : 5,
            "soil_temp"     : 6,
            "air_temp"      : 7,
            "cal_air_temp"  : 8,
            "vwc"           : 9,
            "cal_vwc"       : 10,
            "soil_ec"       : 11,
            "cal_ec_porous" : 12,
            "cal_ea"        : 13,
            "cal_ecb"       : 14,
            "cal_dli"       : 15,
            "node_id"       : 16,
            "lat"           : 17,
            "lon"           : 18,
            "site_name"     : 19,
            "cache_id"      : 20,
        }
 
        if ";" in content:
            content = content[:-1]

        download_args = content.split(',')

        # Parse our argument list
        if len(download_args) > 0:
            for arg in download_args:
                if arg.lower().startswith("limit="):
                    limit = int(arg.split('=')[1])

                elif arg.lower().startswith("start_id="):
                    start_id = int(arg.split('=')[1])

                elif arg.lower().startswith("end_id="):
                    end_id = int(arg.split('=')[1])

                elif arg.lower().startswith("unsent_only="):
                    val = arg.split('=')[1]
                    if val == "True":
                        unsent_only = True
                    else:
                        unsent_only = False

        # Merge ph and parrot flower data here
        db = DryadDatabase()
        if db.connect(self.dbname) == False:
            return False
        
        # Default limit for now is 3
        if limit == None:
            limit = 3
            
        records = db.get_data(limit=limit, summarize=False, start_id=start_id, end_id=end_id, unsent_only=unsent_only, cond=" ts.c_end_time IS NOT NULL ")
        resp_data = []

        # Compose our response content
        for rec in records:
            data = '"ph":"{}","sunlight":"{}","soil_temp":"{}","air_temp":"{}","cal_air_temp":"{}","vwc":"{}","cal_vwc":"{}","soil_ec":"{}","cal_ec_porous":"{}","cal_ea":"{}","cal_ecb":"{}","cal_dli":"{}"'.format( rec[idx["ph"]], rec[idx["sunlight"]], rec[idx["soil_temp"]], rec[idx["air_temp"]], rec[idx["cal_air_temp"]], rec[idx["vwc"]], rec[idx["cal_vwc"]], rec[idx["soil_ec"]], rec[idx["cal_ec_porous"]], rec[idx["cal_ea"]], rec[idx["cal_ecb"]], rec[idx["cal_dli"]] )
            origin = '"name":"{}","lat":"{}","lon":"{}"'.format(rec[idx["node_id"]], rec[idx["lat"]], rec[idx["lon"]])
            resp_data.append( {
                "rec_id": rec[idx['id']],
                "data" : json.loads("{" + data + "}"),
                "origin": json.loads("{" + origin + "}"),
                "timestamp" : rec[idx['end_time']],
                "sampling_site" : rec[idx['site_name']]
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
      
        if unsent_only == True:
            rows_sent = [records[int(idx)][0] for idx in range(len(records))]
            if db.update_sent_rows(rows_sent) == True:
                self.logger.debug("Updating rows sent successful")

        db.disconnect()

        return True

    def handle_request(self, link, request):
        self.logger.info("Message received: {}".format(request))

        req_parts = request.split(':', 1)

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

        elif req_hdr == "QASCP":
            # Add new sampling collection parameters
            if self.handle_req_add_collection_params(link, req_content) == False:
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

