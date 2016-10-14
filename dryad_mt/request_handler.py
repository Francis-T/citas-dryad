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

class RequestHandler():
    def __init__(self, event, queue, state, db_name):
        self.hevent = event
        self.queue = queue
        self.nstate = state
        self.dbname = db_name
        
        self.logger = logging.getLogger("main.RequestHandler")
        return

    def handle_req_state(self, link, content):
        state = self.nstate.get_state()
        return link.send_response("RSTAT:" + state + ";\r\n")

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

    def handle_req_shutdown(self, link, content):
        # Add a deactivation request to the main cache node queue
        self.queue.put("SHUTDOWN")

        # And trigger the event handler
        self.hevent.set()

        return True
        
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
            limit = 20


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
                pp.pprint(resp_data)
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

