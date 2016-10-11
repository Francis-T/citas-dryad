"""
    Name: database.py
    Author: Francis
    Description:
        Source code for the Database controller module
"""
import sqlite3
import time
import logging

DEFAULT_DB_NAME = "dryad_cache.db"
DEFAULT_GET_COND = "C_UPLOAD_TIME IS NULL"

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

    """
        Sets up the data cache table
    """
    def setup_data_table(self):
        # Identify our target table 
        table_name = "t_data_cache"

        # Build up our columns 
        columns = ""
        columns += "C_ID            INTEGER PRIMARY KEY, "
        columns += "C_RETRIEVE_TIME LONG, "
        columns += "C_ORIGIN        VARCHAR, "
        columns += "C_DATA          VARCHAR, "
        columns += "C_UPLOAD_TIME   LONG "

        # Finally, build our query 
        query = "CREATE TABLE {} ({});".format(table_name, columns)

        # Debug Note: This is where you can opt to print out your query 

        # And execute it using our database connection 
        if not self.perform(query):
            return False

        return True

    """
        Sets up the known nodes table
    """
    def setup_known_nodes_table(self):
        # Identify our target table
        table_name = "t_known_nodes"

        # Build up our columns
        columns =  ""
        columns += "C_ID            VARCHAR PRIMARY KEY, "
        columns += "C_NAME          VARCHAR(50), "
        columns += "C_TYPE          VARCHAR(50), "
        columns += "C_CLASS         VARCHAR(50), "
        columns += "C_LAT           FLOAT(8), "
        columns += "C_LON           FLOAT(8), "
        columns += "C_BATT          FLOAT(5), "
        columns += "C_LAST_SCANNED  LONG "

        # Finally, build our query 
        query = "CREATE TABLE {} ({});".format(table_name, columns)

        # And execute it using our database connection 
        if not self.perform(query):
            return False

        return True

    """
        Setup the database if it has not already been so
    """
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

        if self.setup_data_table() == False:
            self.logger.error("Database setup failed")
            return False

        if self.setup_known_nodes_table() == False:
            self.logger.error("Database setup failed")
            return False

        self.logger.info("Database setup succesful")
        return True

    """
        Check if the required tables are already in the database
    """
    def check_tables(self):
        cur = self.dbconn.cursor()
        # Check if the tables we want are already represented in the database 
        try:
            cur.execute("SELECT * FROM t_data_cache")
        except sqlite3.OperationalError:
            return False

        try:
            cur.execute("SELECT * FROM t_known_nodes")
        except sqlite3.OperationalError:
            return False

        return True

    """
        Add data to the t_data_cache table
    """
    def add_data(self, data, source="UNKNOWN", timestamp=-1):
        if not self.dbconn:
            return False

        table_name = "t_data_cache"
        columns = "C_RETRIEVE_TIME, C_ORIGIN, C_DATA"

        # Define the values to be inserted 
        if timestamp <= 0:
            timestamp = int(time.time())

        values = '%li, "%s", "%s"' % (timestamp, source, data)

        # Build our INSERT query 
        query = "INSERT INTO %s (%s) VALUES (?, ?, ?);" % (table_name, columns)

        # And execute it using our database connection 
        return self.perform(query, (int(timestamp), source, data))

    """
        Retrieve data from the t_data_cache table in our database with the ff
        constraints on row return limit, row offset, and filter condition
    """
    def get_data(self, limit=0, offset=0, cond=DEFAULT_GET_COND):
        if not self.dbconn:
            return False

        # Build our SELECT query 
        table_name = "t_data_cache"
        columns = "C_ID, C_ORIGIN, C_RETRIEVE_TIME, C_DATA"
        query = "SELECT %s FROM %s WHERE %s" % (columns, table_name, cond)

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
        except sqlite3.OperationalError:
            #print("Failed to retrieve data")
            return None

        return result

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

    """
        Adds a new node to the t_known_nodes table
    """
    def add_node_info(self, node_id, node_name, node_type):
        if not self.dbconn:
            return False

        table_name = "t_known_nodes"
        columns = "C_ID, C_NAME, C_TYPE, C_LAST_SCANNED"

        # Build our INSERT query
        query = "INSERT INTO {} ({}) VALUES (?, ?, ?, ?);".format(table_name, columns)

        return self.perform(query, (node_id, node_name, node_type, int(time.time())))
        
    """
        Gets stored information on a particular node from the t_known_nodes table in
        the database given a specific node id (e.g. a MAC address)
    """
    def get_node_info(self, node_id):
        if not self.dbconn:
            return False

        table_name = "t_known_nodes"
        columns = "C_ID, C_NAME, C_TYPE, C_CLASS, C_LAT, C_LON, C_BATT, C_LAST_SCANNED"
        condition = 'C_ID = "{}"'.format(node_id)

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

    """
        Gets a list of node ids with node names from the t_known_nodes table in the 
        database given a condition
    """
    def get_nodes(self, condition=None):
        if not self.dbconn:
            return False

        table_name = "t_known_nodes"
        columns = "C_ID, C_NAME, C_TYPE, C_CLASS"

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

    """
        Update node info in the t_knmown_nodes table given a record id
    """
    def update_node(self, node_id, node_name=None, node_type=None, node_class=None, lat=None, lon=None, batt=None, scan=None):
        if not self.dbconn:
            return False

        # Map function arguments to column update templates
        update_map = [
            ( 'C_NAME = "{}"',       node_name ),
            ( 'C_TYPE = "{}"',       node_type ),
            ( 'C_CLASS = "{}"',      node_class ),
            ( 'C_LAT = {}',          lat ),
            ( 'C_LON = {}',          lon ),
            ( 'C_BATT = {}',         batt ),
            ( 'C_LAST_SCANNED = {}', scan ),
        ]
        is_first = True

        # Define the parts of our UPDATE query 
        table_name = "t_known_nodes"
        update = ""
        for template, value in update_map:
            if not value == None:
                if not is_first:
                    update += ", "
                else:
                    is_first = False
                
                update += template.format(value)
        
        condition = 'C_ID = "{}"'.format(node_id)

        # Build our UPDATE query 
        query = "UPDATE {} SET {} WHERE {}".format(table_name, update, condition)

        # And execute it using our database connection 
        return self.perform(query)

    """
        Disconnect from the database
    """
    def disconnect(self):
        if self.dbconn == None:
            return
        self.dbconn.close()

    """
        Execute the query using the provided database connection
    """
    def perform(self, query, extras=None):
        print("Query {" + query + "}")
        try:
            if extras == None:
                self.dbconn.execute(query)
            else:
                self.dbconn.execute(query, extras)

            self.dbconn.commit()
        except sqlite3.OperationalError:           
            self.logger.exception("Query Failed (Operational Error): {}".format(query))
            return False

        except sqlite3.IntegrityError:
            self.logger.exception("Query Failed (Integrity Error): {}".format(query))
            return False

        return True

