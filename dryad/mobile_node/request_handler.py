"""
    Name: request_handler.py
    Author: Jerelyn C / Francis T
    Desc: Source code for the Cache Node request handler
"""
import logging
import json
import pprint
import os
import subprocess

import dryad.sys_info as sys_info

from time import time, ctime

from utils.transform import DataTransformation
from dryad.database import DryadDatabase
from dryad.node_state import NodeState
from dryad.models import NodeDevice
from collections import Iterable

CLASS_SENSOR = "SENSOR"

TYPE_PARROT = "PARROT"
TYPE_BLUNO = "BLUNO"

SYS_CMD_UPTIME = 'uptime | cut -d"," -f1'

class RequestHandler():
    def __init__(self, node):
        self.request_handler_tbl = [
            { "req_hdr" : "QSTAT", "function" : self.handle_req_state },
            { "req_hdr" : "QTSET", "function" : self.handle_req_dtime_set },
            { "req_hdr" : "QACTV", "function" : self.handle_req_activate },
            { "req_hdr" : "QDEAC", "function" : self.handle_req_deactivate },
            { "req_hdr" : "QASCP", "function" : self.handle_req_add_collection_params },
            { "req_hdr" : "QCUPD", "function" : self.handle_req_update_cache },
            { "req_hdr" : "QNLST", "function" : self.handle_req_list_sensors },
            { "req_hdr" : "QQRSN", "function" : self.handle_req_setup_sensor },
            { "req_hdr" : "QSUPD", "function" : self.handle_req_update_sensor },
            { "req_hdr" : "QDLTE", "function" : self.handle_req_remove_sensor },
            { "req_hdr" : "QHALT", "function" : self.handle_req_halt },
            { "req_hdr" : "QRELD", "function" : self.handle_req_reload },
            { "req_hdr" : "QREBT", "function" : self.handle_req_reboot },
            { "req_hdr" : "QPWDN", "function" : self.handle_req_shutdown },
            { "req_hdr" : "QEXTN", "function" : self.handle_req_extend_idle },
            { "req_hdr" : "QSETP", "function" : self.handle_req_set_param },
            { "req_hdr" : "QPARL", "function" : self.handle_req_param_list },
            { "req_hdr" : "QINFO", "function" : self.handle_req_info_list },
            { "req_hdr" : "QDATA", "function" : self.handle_req_download },
        ]

        self.task_node = node
        self.version = self.task_node.get_version()
        self.logger = logging.getLogger("main.RequestHandler")

        return

    def handle_req_state(self, link, content):
        # Retrive details about the cache node from the database
        db = DryadDatabase()
        node_matches = db.get_nodes(node_class='SELF')
        data = db.get_data()
        
        if len(node_matches) <= 0:
            db.close_session()
            self.logger.error("Failed to load data for 'SELF'")

            return link.send_response("RSTAT:FAIL\r\n")

        db.close_session()

        # Retrive uptime
        self_uptime = os.popen(SYS_CMD_UPTIME).read().strip()

        node_data = node_matches[0]

        # Format the string to return
        state =  "'name':'{}','state':'{}','batt':{},'version':'{}',"
        state += "'lat':{},'lon':{},'sys_time':'{}','uptime':'{}',"
        state += "'next_sleep_time':'{}','next_collect_time':'{}',"
        state += "'size':{}"
        state = state.format( node_data.name,
                              self.task_node.get_state_str(),
                              -99.0, 
                              self.version, 
                              node_data.lat, 
                              node_data.lon,
                              ctime(),
                              self_uptime,
                              ctime(self.task_node.get_idle_out_time()),
                              ctime(self.task_node.get_collect_time()),
                              len(data))
        
        return link.send_response("RSTAT:{" + state + "};\r\n")

    def handle_req_dtime_set(self, link, content):
        # splitting arguments
        content = content.strip(';')
        update_args = content.split(',')

        for arg in update_args:
            # date update format
            upd_format = "+%Y%m%d"
     
            val = arg.split('=')[1]

            # change update format to time if time update is being requested
            if "time" in arg:
                upd_format = "+%T"

            date_update_flag = subprocess.call(["sudo", "date", upd_format, '-s', val]) 
            hwclock_update_flag = subprocess.call(["sudo", "hwclock", "-s"])
    
            # check if updating is success
            if date_update_flag & hwclock_update_flag != 0:
                self.logger.error("Failed to update time with request: {}".format(content))
                return link.send_response("QTSET:FAIL;\r\n")

        updated_datetime = subprocess.check_output(["sudo", "hwclock"]) 
        self.logger.info("Datetime updated to {}".format(updated_datetime))
        return link.send_response("QTSET:OK;\r\n")
 
    def handle_req_param_list(self, link, content):
        params = None

        db = DryadDatabase()
        params = db.get_all_system_params()
        db.close_session()

        param_list = {}
        for p in params:
            param_list[p.name] = p.value

        return link.send_response("RPARL:{};\r\n".format(param_list))

    def handle_req_info_list(self, link, content):
        params = None

        db = DryadDatabase()
        params = db.get_all_system_info()
        db.close_session()

        param_list = {}
        for p in params:
            param_list[p.name] = p.value

        return link.send_response("RINFO:{};\r\n".format(param_list))

    def handle_req_activate(self, link, content):
        # TODO Add activation task to task node
        self.task_node.add_task("ACTIVATE")

        return link.send_response("RACTV:OK;\r\n")

    def handle_req_deactivate(self, link, content):
        # TODO Add deactivation task to task node
        self.task_node.add_task("DEACTIVATE")
       
        return link.send_response("RDEAC:OK;\r\n")

    def handle_req_add_collection_params(self, link, content):
        # remove trailing ";" 
        content = content.strip(';')

        params_args = content.split(',')

        # Parse our argument list
        if len(params_args) > 0:
            for arg in params_args:
                param_key = arg.split('=')[0].strip()
                param_val = arg.split('=')[1].strip()
       
                sys_info.set_param(param_key, param_val)

        # TODO Trigger parameter reload on the task node
        self.task_node.add_task("RELOAD_PARAMS")
        
        return link.send_response("RASCP:OK;\r\n")

    def handle_req_update_cache(self, link, content):
        params = {
            "name"      :   None, 
            "lat"       :   None, 
            "lon"       :   None, 
            "site_name" :   None
        }

        # remove trailing ";" 
        content = content.strip(';')

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
        node_matches = db.get_nodes(node_class='SELF')
        if len(node_matches) <= 0:
            self.logger.error("Failed to load data for 'SELF'")
            db.close_session()

            return link.send_response("RCUPD:FAIL;\r\n")

        # Extract only the relevant node record
        node_data = node_matches[0]

        # Update cache node details in the DB
        result = db.insert_or_update_node( name = node_data.name,
                                           node_class = node_data.node_class,
                                           site_name = params['site_name'],
                                           lat = params['lat'],
                                           lon = params['lon'] )

        db.close_session()

        if result == False:
            self.logger.error("Failed to update cache node details")
            link.send_response("RCUPD:FAIL;\r\n")
            return False

        return link.send_response("RCUPD:OK;\r\n")

    def handle_req_list_sensors(self, link, content):
        db = DryadDatabase()
        node_matches = db.get_nodes(node_class='SENSOR')

        sensors = "{'sensors':["
        if len(node_matches) <= 0:
            sensors += "]}"
            db.close_session()
            return link.send_response("RNLST:" + sensors + ";\r\n")

        snode_list = []
        for node in node_matches:
            pf_addr = "????"
            bl_addr = "????"
            pf_batt = -99.0
            bl_batt = -99.0

            # Get the matching devices sharing the node's name
            device_matches = db.get_devices(name=node.name)
            if device_matches == None:
                self.logger.warn("Node does not have any associated devices: {}"
                                    .format(node.name))
                continue

            if len(device_matches) <= 0:
                self.logger.warn("Node does not have any associated devices: {}"
                                    .format(node.name))
                continue

            # For each matching device, extract the parrot fp address and the
            #   bluno address and then store them in separate variables
            for device in device_matches:
                device_type = str(device.device_type.name)
                if device_type == 'BLUNO':
                    bl_addr = device.address

                elif device_type == "PARROT":
                    pf_addr = device.address
                    pf_batt = device.power

            snode = "'name':'{}', 'state':'{}',"
            snode += "'site_name':'{}','lat':'{}', 'lon':'{}',"
            snode += "'pf_addr':'{}', 'bl_addr':'{}', 'pf_batt':'{}',"
            snode += "'bl_batt':'{}', 'pf_comms':'{}', 'bl_comms':'{}'"

            snode = snode.format( node.name,
                                  self.task_node.get_state_str(),
                                  node.site_name,
                                  node.lat,
                                  node.lon,
                                  pf_addr,
                                  bl_addr,
                                  pf_batt,
                                  -99.0,
                                  ctime(0.0),
                                  ctime(0.0) )

            snode_list.append( "{" + snode + "}" )
        
        # Build the sensor node list string
        snodes_all = ",".join(snode_list)

        # Build the final string
        sensors += snodes_all
        sensors += "]}"
   
        # print(sensors)

        db.close_session()
         
        return link.send_response("RNLST:" + sensors + ";\r\n")
   
    def handle_req_setup_sensor(self, link, content):
        params = {
            "name"          : None, 
            "site_name"     : None, 
            "pf_addr"       : None, 
            "bl_addr"       : None,
            "state"         : None,
            "lat"           : None,
            "lon"           : None, 
            "updated"       : None,
        }

        # remove trailing ";" 
        if ";" in content:
            content = content[:-1]

        update_args = content.split(',')
        
        # TODO WTF is this magickery???
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
        dt = DataTransformation()
        bl_addr = dt.conv_mac(params["bl_addr"].upper())
        pf_addr = dt.conv_mac(params["pf_addr"].upper())

        result = db.insert_or_update_node( name         = params['name'],
                                           node_class   = CLASS_SENSOR,
                                           site_name    = params['site_name'],
                                           lat          = params['lat'],
                                           lon          = params['lon'] )
        if result == False:
            self.logger.error("Failed to add node")
            link.send_response("RQRSN:FAIL;\r\n")
            db.close_session()
            return False

        result = db.insert_or_update_device( address        = bl_addr,
                                             node_id        = params['name'],
                                             device_type    = TYPE_BLUNO )
        if result == False:
            self.logger.error("Failed to add node device")
            link.send_response("RQRSN:FAIL;\r\n")
            db.close_session()
            return False

        result = db.insert_or_update_device( address        = pf_addr,
                                             node_id        = params['name'],
                                             device_type    = TYPE_PARROT )
        if result == False:
            self.logger.error("Failed to add node device")
            link.send_response("RQRSN:FAIL;\r\n")
            db.close_session()
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
        dt = DataTransformation()
        result = db.insert_or_update_node( name         = params['name'],
                                           node_class   = CLASS_SENSOR,
                                           site_name    = params['site_name'],
                                           lat          = params['lat'],
                                           lon          = params['lon'] )
        if result == False:
            self.logger.error("Failed to add node")
            link.send_response("RSUPD:FAIL;\r\n")
            db.close_session()
            return False

        db.close_session()

        return link.send_response("RSUPD:OK;\r\n")

    def handle_req_remove_sensor(self, link, content):
        params = {
            "rpi_name"    : None, 
            "sn_name"   : None, 
        }
        
        content = content.strip(";")
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
        result = db.delete_device(params["sn_name"])
        if result == False:
            self.logger.error("Failed to remove device")
            link.send_response("RDLTE:FAIL;\r\n")
            db.close_session()
            return False

        result = db.delete_node(params["sn_name"])
        if result == False:
            self.logger.error("Failed to remove node")
            link.send_response("RDLTE:FAIL;\r\n")
            db.close_session()
            return False

        db.close_session()

        return link.send_response("RDLTE:OK;\r\n")

    def handle_req_halt(self, link, content):
        # Add a halt/suspend task to the task node
        self.task_node.add_task("SUSPEND")

        return link.send_response("RHALT:OK;\r\n")

    def handle_req_reload(self, link, content):
        # Add a reload task to the task node
        self.task_node.add_task("RELOAD")

        return link.send_response("RRELD:OK;\r\n")

    def handle_req_reboot(self, link, content):
        # Add a reboot task to the task node
        self.task_node.add_task("REBOOT")

        return link.send_response("RREBT:OK;\r\n")

    def handle_req_shutdown(self, link, content):
        # Add a shutdown task to the task node
        self.task_node.add_task("SHUTDOWN")

        return link.send_response("RPWDN:OK;\r\n")

    def handle_req_extend_idle(self, link, content):
        # Add extend idle time task to the task node
        self.task_node.add_task("EXTEND_IDLE")

        return link.send_response("REXTI:OK;\r\n")

    def handle_req_set_param(self, link, content):
        # Add extend idle time task to the task node

        self.task_node.add_task("SET_PARAMS " + content)

        return link.send_response("RSETP:OK;\r\n")

    def handle_req_download(self, link, content):

        limit = None
        offset = None
        start_id = 0
        end_id = 100000000000000

        # Parse our argument list
        download_args = content.split(',')
        if len(download_args) > 0:
            for arg in download_args:
                if arg.lower().startswith("limit="):
                    limit = int(arg.split('=')[1])

                elif arg.lower().startswith("start_id="):
                    start_id = int(arg.split('=')[1])

                elif arg.lower().startswith("end_id="):
                    end_id = int(arg.split('=')[1])

                elif arg.lower().startswith("offset="):
                    offset = int(arg.split('=')[1])

        db = DryadDatabase()
        matched_data = db.get_data(limit=limit,
                                   offset=offset,
                                   start_id=start_id,
                                   end_id=end_id)
        db.close_session()

        data = []
        data_str = ""
        data_block = {}
        for reading in matched_data:
            # TODO Format it here
            data_block['rec_id'] = reading.id
            data_block['timestamp'] = reading.end_time
            data_block['sampling_site'] = reading.site_name # TODO
            data_block['data'] = json.loads(reading.content.replace("'",'"'))
            data_block['origin'] = { 'name' : reading.name, 
                                     'lat'  : reading.lat,
                                     'lon'  : reading.lon,
                                     'addr' : "---" }


            if 'ph' not in data_block['data']:
                data_block['data']['ph'] = None

            if 'bl_batt' not in data_block['data']:
                data_block['data']['bl_batt'] = None

            data.append(data_block)

            data_block = {}

        return link.send_response("RDATA:{};\r\n".format(json.dumps(data)))

    def handle_request(self, link, request):
        self.logger.info("Message received: {}".format(request))

        req_parts = request.split(':', 1)

        if not len(req_parts) == 2:
            self.logger.error("Malformed request: {}".format(request))
            return False

        req_hdr = req_parts[0]
        req_content = req_parts[1].strip().strip(';')

        result = False
        for handler in self.request_handler_tbl:
            if req_hdr == handler['req_hdr']:
                result = handler['function'](link, req_content)

        if result == False:
            self.logger.error("Failed to handler {} request".format(req_hdr))

        return result

