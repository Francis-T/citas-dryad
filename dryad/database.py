"""
    Name: database.py
    Author: Jerelyn C / Francis
    Description:
        Source code for the Database controller module
"""
import sqlite3
import time
import logging
import json
import dryad.custom_ble as ble

DEFAULT_DB_NAME = "dryad_cache.db"
DEFAULT_GET_COND = "c_content IS NOT NULL"

module_logger = logging.getLogger("main.database")

class DryadDatabase():
    def __init__(self):
        self.db_name = ""
        self.dbconn = None
        self.logger = logging.getLogger("main.database.DryadDatabase")

    """
        Connect to the database
    """
    def connect(self, db_name=DEFAULT_DB_NAME):
        self.dbconn = sqlite3.connect(db_name)
        return self.dbconn

    # @desc     Disconnects from the database
    # @return   None
    def disconnect(self):
        if self.dbconn == None:
            return
        self.dbconn.close()
        return

    # @desc     Executes the query using the provided database connection
    # @return   A boolean indicating success or failure
    def perform(self, query, extras=None):
        result = False
        try:
            if extras == None:
                result = self.dbconn.execute(query)
            else:
                result = self.dbconn.execute(query, extras)

            self.dbconn.commit()
        except sqlite3.OperationalError:           
            self.logger.exception("Query Failed (Operational Error): {}".format(query))
            return False

        except sqlite3.IntegrityError:
            self.logger.exception("Query Failed (Integrity Error): {}".format(query))
            return False

        if not result == True and not result == False:
            return result.fetchall()

        return True

    ##********************************##
    ##  SEC01: Table Setup Functions  ##
    ##******************************* ##
    # @desc     Setup the capture session table to track individual
    #           sensor read sessions
    # @return   A boolean indicating success or failure
    def setup_sessions_table(self):
        # Identify our target table 
        table_name = "t_session"

        # Build up our columns 
        columns = ""
        columns += "c_id            INTEGER PRIMARY KEY, "
        columns += "c_start_time    LONG, "
        columns += "c_end_time      LONG "

        # Finally, build our query 
        query = "CREATE TABLE {} ({});".format(table_name, columns)

        # Debug Note: This is where you can opt to print out your query 

        # And execute it using our database connection 
        return self.perform(query)


    # @desc     Setup the sensor data cache table
    # @return   A boolean indicating success or failure
    def setup_data_cache_table(self):
        # Identify our target table 
        table_name = "t_data_cache"

        # Build up our columns 
        columns = ""
        columns += "c_id            INTEGER PRIMARY KEY, "
        columns += "c_session_id    INTEGER, "
        columns += "c_source        VARCHAR, "
        columns += "c_dest          VARCHAR, "
        columns += "c_content       VARCHAR, "
        ## Adding columns for an column-based content 
        columns += "c_sunlight      FLOAT(8), "
        columns += "c_soil_temp     FLOAT(8), "
        columns += "c_air_temp      FLOAT(8), "
        columns += "c_cal_air_temp  FLOAT(8), "
        columns += "c_vwc           FLOAT(8), "
        columns += "c_cal_vwc       FLOAT(8), "
        columns += "c_soil_ec       FLOAT(8), "
        columns += "c_cal_ec_porous FLOAT(8), "
        columns += "c_cal_ea        FLOAT(8), "
        columns += "c_cal_ecb       FLOAT(8), "
        columns += "c_cal_dli       FLOAT(8), "
        columns += "c_ph            FLOAT(8), "
        columns += "c_upload_time   LONG, "
        columns += "FOREIGN KEY(c_session_id) "
        columns += "    REFERENCES t_session(c_id), "
        columns += "FOREIGN KEY(c_source) "
        columns += "    REFERENCES t_node(c_node_id), "
        columns += "FOREIGN KEY(c_dest) "
        columns += "    REFERENCES t_node(c_node_id) "

        # Finally, build our query 
        query = "CREATE TABLE {} ({});".format(table_name, columns)

        # Debug Note: This is where you can opt to print out your query 

        # And execute it using our database connection 
        return self.perform(query)

    # @desc     Setup the node table
    # @return   A boolean indicating success or failure
    def setup_nodes_table(self):
        # Identify our target table
        table_name = "t_node"

        # Build up our columns
        columns =  ""
        columns += "c_node_id       VARCHAR(50) PRIMARY KEY, "
        columns += "c_class         VARCHAR(50), "
        columns += "c_site_name     VARCHAR(50), "
        columns += "c_date_updated  LONG"

        # Finally, build our query 
        query = "CREATE TABLE {} ({});".format(table_name, columns)

        # And execute it using our database connection 
        return self.perform(query)

    # @desc     Setup the node device table
    # @return   A boolean indicating success or failure
    def setup_node_devices_table(self):
        # Identify our target table
        table_name = "t_node_device"

        # Build up our columns
        columns =  ""
        columns += "c_addr          VARCHAR(17) PRIMARY KEY, "
        columns += "c_node_id       VARCHAR(50), "
        columns += "c_type          VARCHAR(50), "
        columns += "c_state         VARCHAR(20), "
        columns += "c_batt          FLOAT(5), "
        columns += "c_lat           FLOAT(8), "
        columns += "c_lon           FLOAT(8), "
        columns += "c_last_scanned  LONG, "
        columns += "c_last_comms    LONG, "
        columns += "c_last_updated  LONG, "
        columns += "FOREIGN KEY(c_node_id) "
        columns += "    REFERENCES t_node(c_node_id) "

        # Finally, build our query 
        query = "CREATE TABLE {} ({});".format(table_name, columns)

        # And execute it using our database connection 
        return self.perform(query)

    # @desc     Setup the entire database
    # @return   A boolean indicating success or failure
    def setup(self):
        # Check if this database object is valid 
        if self.dbconn == None:
            self.logger.error("Invalid database")
            return False

        # Check if the required tables already exist. If so, return early 
        if self.check_tables():
            self.logger.debug("Database already set up")
            return True
        else:
            self.logger.debug("Database not yet set up")

        self.logger.info("Setting up the database...")

        if self.setup_nodes_table() == False:
            self.logger.error("Database setup failed: Nodes")
            return False

        if self.setup_sessions_table() == False:
            self.logger.error("Database setup failed: Sessions")
            return False

        if self.setup_node_devices_table() == False:
            self.logger.error("Database setup failed: Node Devices")
            return False

        if self.setup_data_cache_table() == False:
            self.logger.error("Database setup failed: Data Cache")
            return False

        self.logger.info("Database setup succesful")
        return True

    # @desc     Check if the required tables are already present in the DB
    # @return   A boolean indicating success or failure
    def check_tables(self):
        cur = self.dbconn.cursor()
        # Check if the tables we want are already represented in the database 
        try:
            cur.execute("SELECT * FROM t_data_cache")
        except sqlite3.OperationalError:
            return False

        try:
            cur.execute("SELECT * FROM t_node")
        except sqlite3.OperationalError:
            return False

        try:
            cur.execute("SELECT * FROM t_node_device")
        except sqlite3.OperationalError:
            return False

        try:
            cur.execute("SELECT * FROM t_session")
        except sqlite3.OperationalError:
            return False

        return True

    ##**********************************##
    ##  SEC02: Record Insert Functions  ##
    ##********************************* ##
    # @desc     Adds new node information to the table
    # @return   A boolean indicating success or failure
    def add_node(self, node_id, node_class, site_name = None, date_updated = None):
        if not self.dbconn:
            return False

        table_name = "t_node"
        columns = "c_node_id, c_class, c_site_name, c_date_updated"
        values = (node_id, node_class, site_name, date_updated)

        # Build our INSERT query 
        query = "INSERT INTO {} ({}) VALUES (?, ?, ?, ?);".format(table_name, columns)

        # And execute it using our database connection 
        return self.perform(query, values)

    # @desc     Adds new node device information to the table
    # @return   A boolean indicating success or failure
    def add_node_device(self, node_addr, node_id, node_type, battery= 0, lat = 0, lon = 0, last_scanned = 0, last_comms = 0, last_updated = 0, state = "UNKNOWN"):
        if not self.dbconn:
            return False

        table_name = "t_node_device"
        columns = "c_addr, c_node_id, c_type, c_batt, c_lat, c_lon, c_last_scanned, c_last_comms, c_last_updated, c_state"
        values = (node_addr, node_id, node_type, battery, lat, lon, last_scanned, last_comms, last_updated, state)

        # Build our INSERT query 
        query = "INSERT INTO {} ({}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);".format(table_name, columns)

        # And execute it using our database connection 
        return self.perform(query, values)

    # @desc     Starts a new sensor data capture session
    # @return   A boolean indicating success or failure
    def start_capture_session(self):
        if not self.dbconn:
            return False

        table_name = "t_session"
        columns = "c_start_time"
        values = str( int(time.time()) ) 

        # Build our INSERT query 
        query = "INSERT INTO {} ({}) VALUES ({});".format(table_name, columns, values)

        # And execute it using our database connection 
        return self.perform(query)

    # @desc     Adds / Updates a new sensor data record to the table
    # @return   A boolean indicating success or failure
    def add_data(self, session_id, source, content, node_type, dest=","):
        if not self.dbconn:
            return False

        # Initializing flags on which data row to retrieve and update
        lackingBluno = False
        lackingParrot = False
       
        # Converting back content to its json format
        content = json.loads(content)
        
        # Setting up flags for data retrieval
        if node_type == ble.NTYPE_BLUNO:
            lackingBluno = True
        elif node_type == ble.NTYPE_PARROT:
            lackingParrot = True

        # Retrieving last row with no parrot XOR no bluno data
        last_row_arr = self.get_data(session_id=session_id, node_id=source, limit=1, lacksBluno=lackingBluno, lacksParrot=lackingParrot)
        # If return is not empty, then there is a row to update 
        if last_row_arr != []:
            last_data = last_row_arr[0]
            last_data_id = last_data[0]
            if lackingBluno:
                self.update_data(data_id=last_data_id, node_type=node_type, ph=content["PH"]) 
            elif lackingParrot:
                self.update_data(data_id=last_data_id, node_type=node_type, sunlight=content["SUNLIGHT"], soil_temp=content["SOIL_TEMP"], air_temp=content["AIR_TEMP"], cal_air_temp=content["CAL_AIR_TEMP"], vwc=content["VWC"], cal_vwc=content["CAL_VWC"], soil_ec=content["SOIL_EC"], cal_ec_porous=content["CAL_EC_POROUS"], cal_ea=content["CAL_EA"], cal_ecb=content["CAL_ECB"], cal_dli=content["CAL_DLI"]) 
            return     
      
        
        # There is no row to update, continue to create new row
        table_name = "t_data_cache"
        # Varying insert values and query depending from the data source
        if node_type == ble.NTYPE_BLUNO:
            columns = "c_session_id, c_source, c_dest, c_content, c_ph, c_upload_time"
            values = (session_id, source, dest, str(content), content["PH"], str( int(time.time()) )) 
            query = "INSERT INTO {} ({}) VALUES (?, ?, ?, ?, ?, ?);".format(table_name, columns)
        elif node_type == ble.NTYPE_PARROT:
            columns = "c_session_id, c_source, c_dest, c_content, c_sunlight, c_soil_temp,"
            columns += "c_air_temp, c_cal_air_temp, c_vwc, c_cal_vwc, c_soil_ec, c_cal_ec_porous,"
            columns += "c_cal_ea, c_cal_ecb, c_cal_dli, c_upload_time"
            values = (session_id, source, dest, str(content), content["SUNLIGHT"], content["SOIL_TEMP"], content["AIR_TEMP"], content["CAL_AIR_TEMP"], content["VWC"], content["CAL_VWC"], content["SOIL_EC"], content["CAL_EC_POROUS"], content["CAL_EA"], content["CAL_ECB"], content["CAL_DLI"], str( int(time.time()) )) 
            query = "INSERT INTO {} ({}) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);".format(table_name, columns)

        # And execute it using our database connection 
        return self.perform(query, values)

    ##*************************************##
    ##  SEC03: Record Retrieval Functions  ##
    ##************************************ ##
    # @desc     Gets the current session ID
    # @return   A boolean indicating success or failure
    def get_current_session(self):
        query = "SELECT c_id FROM t_session WHERE c_end_time IS NULL"
        result = self.perform(query)
        if result == True or result == False:
            return None

        if len(result) == 0:
            return None

        return result[0][0]

    # @desc     Gets the latest session ID
    # @return   A boolean indicating success or failure
    def get_latest_session(self):
        query = "SELECT c_id FROM t_session ORDER BY c_id DESC LIMIT 1"
        result = self.perform(query)
        if result == True or result == False:
            return None

        if len(result) == 0:
            return None

        return result[0][0]

    # @desc     Retrieve data from the t_data_cache table in our database with the ff
    #           constraints on row return limit, row offset, and filter condition
    # @return   A boolean indicating success or failure
    def get_data(self, session_id=None, node_id=None, limit=0, offset=0, cond=DEFAULT_GET_COND, summarize=False, lacksParrot=False, lacksBluno=False):
        if not self.dbconn:
            return False

        # Retrieving row that lacks bluno data
        if lacksBluno == True:
            cond = "c_source IS '{}' AND c_session_id IS {} AND c_ph IS NULL".format(node_id, session_id)
        # Retrieving row that lacks parrot data
        if lacksParrot == True:
            cond = "c_source IS '{}' AND c_session_id IS {} AND c_soil_temp IS NULL".format(node_id, session_id)

        # Returning summarized data
        if summarize == True:
            return self.get_summarized_data(limit, offset, cond)

        # Build our SELECT query 
        table_name = "t_data_cache AS td JOIN t_session AS ts ON td.c_session_id IS ts.c_id "
        table_name += "JOIN t_node AS tn ON tn.c_node_id IS td.c_source JOIN t_node_device AS "
        table_name += "tnd ON tnd.c_node_id IS tn.c_node_id"
        columns = "td.c_id, td.c_source, ts.c_end_time, td.c_content, td.c_dest, td.c_ph, "
        columns += "td.c_sunlight, td.c_soil_temp, td.c_air_temp, td.c_cal_air_temp, td.c_vwc, "
        columns += "td.c_cal_vwc, td.c_soil_ec, td.c_cal_ec_porous, td.c_cal_ea, td.c_cal_ecb, "
        columns += "td.c_cal_dli, tnd.c_node_id, tnd.c_lat, tnd.c_lon" 
        
        query = "SELECT %s FROM %s WHERE %s ORDER BY td.c_id DESC" % (columns, table_name, cond)

        # Set our offset 
        if limit == 0:
            query += ";"
        else:
            query += " LIMIT %i OFFSET %i;" % (limit, offset)

        cur = self.dbconn.cursor()
        result = None
        try:
            cur.execute(query)
            result = cur.fetchall()
        except sqlite3.OperationalError as e:
            print( "Failed to retrieve data: " + str(e) )
            return None 

        return result

    # TODO
    def get_summarized_data(self, limit=0, offset=0, cond=DEFAULT_GET_COND):
        if not self.dbconn:
            return False

        last_session_id = self.get_latest_session()

        # Build our SELECT query 
        table_name = "t_data_cache AS td JOIN t_session AS ts ON td.c_session_id = ts.c_id"
        columns = "td.c_session_id, ' ', MAX(ts.c_end_time), GROUP_CONCAT(td.c_content,', '), ' '"
        grouping = "td.c_session_id"
        cond = "td.c_session_id = (SELECT MAX(td1.c_session_id) FROM t_data_cache AS td1)"
        query = "SELECT {} FROM {} WHERE {} GROUP BY {}".format(columns, table_name, cond, grouping)

        # Set our offset 
        if limit == 0:
            query += ";"
        else:
            query += " LIMIT %i OFFSET %i;" % (limit, offset)

        cur = self.dbconn.cursor()
        result = None
        try:
            cur.execute(query)
            result = cur.fetchall()
        except sqlite3.OperationalError as e:
            print( "Failed to retrieve data: " + str(e) )
            return None

        return result

    # @desc        Queries in the database the details of self - cache node
    #
    # @return    Returns the list of the results containing details
    def get_self_details(self):
        if not self.dbconn:
            return False

        table_name = "t_node_device"
        columns =   "c_node_id, c_lat, c_lon, c_batt, c_last_scanned, c_last_comms"
        condition = 'c_type = "SELF"'

        # Build our SELECT query 
        query = "SELECT %s FROM %s WHERE %s" % (columns, table_name, condition)

        cur = self.dbconn.cursor()
        result = None
        try:
            cur.execute(query)
            result = cur.fetchall()
        except sqlite3.OperationalError:
            print("Failed to retrieve data")
            return None
        return result[0]
    
    # @desc        Queries in the database the details of self - cache node
    #
    # @return    Returns the list of the results containing details
    def update_self_details(self, node_id=None, lat=None, lon=None, last_scanned=None, last_comms=None, site_name=None, state=None):
        if not self.dbconn:
            return False
        
        update_map = [
        #    ( 'c_node_id = "{}"',    node_id ),
            ( 'c_lat = {}',        lat ),
            ( 'c_lon = {}',        lon ),
            ( 'c_last_scanned = {}',    last_scanned),
            ( 'c_last_comms = {}', last_comms),
        ]

        is_first = True
       
        table_name = "t_node_device"
        
        update = ""
        for template, value in update_map:
            if not value == None:
                if not is_first: 
                    update += ", "
                else:
                    is_first = False
            
                update += template.format(value)

        condition = 'c_node_id = "{}"'.format(node_id)

        # Build our SELECT query 
        query = "UPDATE {} SET {} WHERE {}".format(table_name, update, condition)

        result = self.perform(query)

        if (result == False):
            return result
        
        update_map = [
            ( 'c_site_name = "{}"',    site_name ),
            ( 'c_date_updated = {}', int(time.time()) ),
        ]

        is_first = True
       
        table_name = "t_node"
        
        update = ""
        for template, value in update_map:
            if not value == None:
                if not is_first: 
                    update += ", "
                else:
                    is_first = False
            
                update += template.format(value)

        condition = 'c_node_id = "{}"'.format(node_id)

        # Build our SELECT query 
        query = "UPDATE {} SET {} WHERE {}".format(table_name, update, condition)

        return self.perform(query)

    
    # @desc     Gets stored information on a particular node from the t_known_nodes table in
    #           database given a specific node id (e.g. a MAC address)
    # @return   TODO
    def get_node_device(self, device_addr):
        if not self.dbconn:
            return False

        table_name = "t_node_device"
        columns =   "c_addr, c_node_id, c_type, c_batt, "
        columns +=  "c_lat, c_lon, c_last_scanned, c_last_comms "
        condition = 'c_addr = "{}"'.format(device_addr)

        # Build our SELECT query 
        query = "SELECT %s FROM %s WHERE %s" % (columns, table_name, condition)

        cur = self.dbconn.cursor()
        result = None
        try:
            cur.execute(query)
            result = cur.fetchall()
        except sqlite3.OperationalError:
            #print("Failed to retrieve data")
            return None

        return result

    # @desc     Gets a list of node ids with node names from the t_known_nodes table in the 
    #           database given a condition
    # @return   
    def get_nodes(self, condition=None):
        if not self.dbconn:
            return False

        table_name = "t_node AS tn JOIN t_node_device AS td ON tn.c_node_id = td.c_node_id"
        columns =   "td.c_addr, td.c_node_id, td.c_type, td.c_lat, td.c_lon, td.c_batt, "
        columns +=  "tn.c_site_name, td.c_last_updated, td.c_last_scanned, td.c_last_comms, "
        columns +=  "td.c_state, tn.c_class"
        order = "td.c_node_id, td.c_type"

        # Build our SELECT query 
        query = "SELECT %s FROM %s WHERE %s ORDER BY %s;" % (columns, table_name, condition, order)
        cur = self.dbconn.cursor()
        result = None
        try:
            cur.execute(query)
            result = cur.fetchall()
        except sqlite3.OperationalError:
            #print("Failed to retrieve data")
            return None
        return result


    ##**********************************##
    ##  SEC04: Record Update Functions  ##
    ##********************************* ##
    """
        Flag data in the t_data_cache table as uploaded given a record id
    """
    def set_data_uploaded(self, rec_id):
        if not self.dbconn:
            return False

        # Define the parts of our UPDATE query 
        table_name = "t_data_cache"
        update = "C_UPLOAD_TIME = %li" % (int(time.time()))
        condition = "C_ID = %i" % (rec_id)

        # Build our UPDATE query 
        query = "UPDATE %s SET %s WHERE %s" % (table_name, update, condition)

        # And execute it using our database connection 
        return self.perform(query)

    # @desc     Ends an ongoing sensor data capture session
    # @return   A boolean indicating success or failure
    def end_capture_session(self):
        if not self.dbconn:
            return False

        table_name = "t_session"
        update = "c_end_time = {}".format(int(time.time()))
        condition = "c_end_time IS NULL"

        # Build our INSERT query 
        query = "UPDATE {} SET {} WHERE {};".format(table_name, update, condition)

        # And execute it using our database connection 
        return self.perform(query)

    """
        Update node info in the t_knmown_nodes table given a record id
    """
    def update_node_device(self, node_id=None, node_addr=None, node_type=None, lat=None, lon=None, batt=None, scan=None, comms=None, updated=None):
        if not self.dbconn:
            return False

        # Map function arguments to column update templates
        update_map = [
            ( 'c_addr = "{}"',       node_addr ),
            ( 'c_type = "{}"',       node_type ),
            ( 'c_lat = {}',          lat ),
            ( 'c_lon = {}',          lon ),
            ( 'c_batt = {}',         batt ),
            ( 'c_last_scanned = {}', scan ),
            ( 'c_last_comms = {}',   comms ),
            ( 'c_last_updated = {}', updated ),
        ]
        is_first = True

        # Define the parts of our UPDATE query 
        table_name = "t_node_device"
        update = ""
        for template, value in update_map:
            if not value == None:
                if not is_first:
                    update += ", "
                else:
                    is_first = False
                
                update += template.format(value)
        
        condition = 'c_node_id = "{}"'.format(node_id)

        # Build our UPDATE query 
        query = "UPDATE {} SET {} WHERE {}".format(table_name, update, condition)

        # And execute it using our database connection 
        return self.perform(query)

    def update_node(self, node_id=None, node_class=None, site_name=None):
        if not self.dbconn:
            return False

        # Map function arguments to column update templates
        update_map = [
            ( 'c_site_name = "{}"',   site_name ),
            ( 'c_class = "{}"',      node_class ),
            ( 'c_date_updated = "{}"', int(time.time()) ),
        ]
        is_first = True

        # Define the parts of our UPDATE query 
        table_name = "t_node"
        update = ""
        for template, value in update_map:
            if not value == None:
                if not is_first:
                    update += ", "
                else:
                    is_first = False
                
                update += template.format(value)
        
        condition = 'c_node_id = "{}"'.format(node_id)

        # Build our UPDATE query 
        query = "UPDATE {} SET {} WHERE {}".format(table_name, update, condition)

        # And execute it using our database connection 
        return self.perform(query)


    def update_data(self, data_id=None, node_type=ble.NTYPE_PARROT, sunlight=None, soil_temp=None, air_temp=None, cal_air_temp=None, vwc=None, cal_vwc=None, soil_ec=None, cal_ec_porous=None, cal_ea=None, cal_ecb=None, cal_dli=None, ph=None):
        
        if not self.dbconn:
            return False

        # Map function arguments to column update templates
        if node_type == ble.NTYPE_PARROT: 
            update_map = [
                ( 'c_sunlight = "{}"',      sunlight        ),
                ( 'c_soil_temp = "{}"',     soil_temp       ),
                ( 'c_air_temp = "{}"',      air_temp        ),
                ( 'c_cal_air_temp = "{}"',  cal_air_temp    ),
                ( 'c_vwc= "{}"',            vwc             ),
                ( 'c_cal_vwc= "{}"',        cal_vwc         ),
                ( 'c_soil_ec= "{}"',        soil_ec         ),
                ( 'c_cal_ec_porous= "{}"',  cal_ec_porous   ),
                ( 'c_cal_ea= "{}"',         cal_ea          ),
                ( 'c_cal_ecb= "{}"',        cal_ecb         ),
                ( 'c_cal_dli= "{}"',        cal_dli         ),
            ]
        
        if node_type == ble.NTYPE_BLUNO:
            update_map = [
                ( 'c_ph = "{}"',            ph              ),
            ]

        is_first = True

        # Define the parts of our UPDATE query 
        table_name = "t_data_cache"
        update = ""
        for template, value in update_map:
            if not value == None:
                if not is_first:
                    update += ", "
                else:
                    is_first = False
                
                update += template.format(value)
        
        condition = 'c_id = "{}"'.format(data_id)

        # Build our UPDATE query 
        query = "UPDATE {} SET {} WHERE {}".format(table_name, update, condition)

        # And execute it using our database connection 
        return self.perform(query)

    def remove_node(self, node_id=None, node_class="SENSOR"):
        if not self.dbconn:
            return False

        table_name = 't_node_device'
        if node_class == "SELF":
            table_name = 't_node'
        
        condition = 'c_node_id = "{}"'.format(node_id)

        # Build our DELETE query 
        query = "DELETE FROM {} WHERE {}".format(table_name, condition)

        # And execute it using our database connection 
        return self.perform(query)


