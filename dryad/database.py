"""
    Name: database.py
    Author: Francis
    Description:
        Source code for the Database controller module
"""
import sqlite3
import time

DEFAULT_DB_NAME = "dryad_cache.db"
DEFAULT_GET_COND = "C_UPLOAD_TIME IS NULL"

class DryadDatabase():
    def __init__(self):
        self.db_name = ""
        self.dbconn = None

    """ Connect to the database """
    def connect(self, db_name=DEFAULT_DB_NAME):
        self.dbconn = sqlite3.connect(db_name)
        return self.dbconn

    """ Setup the database if it has not already been so """
    def setup(self):
        """ Check if this database object is valid """
        if self.dbconn == None:
            print("Invalid database")
            return False

        """ Check if the required tables already exist. If so, return early """
        if self.check_tables():
            print("Database already set up")
            return True
        else:
            print("Database not yet set up")

        print("Setting up the database...")

        """ Identify our target table """
        table_name = "t_data_cache"

        """ Build up our columns """
        columns = ""
        columns += "C_ID            INTEGER PRIMARY KEY, "
        columns += "C_RETRIEVE_TIME LONG, "
        columns += "C_ORIGIN        VARCHAR, "
        columns += "C_DATA          VARCHAR, "
        columns += "C_UPLOAD_TIME   LONG "

        """ Finally, build our query """
        query = "CREATE TABLE %s (%s);" % (table_name, columns)

        """ Debug Note: This is where you can opt to print out your query """

        """ And execute it using our database connection """
        if not self.perform(query):
            print("Database setup failed")
            return False

        print("Database setup succesful")
        return True

    """ Check if the required tables are already in the database """
    def check_tables(self):
        cur = self.dbconn.cursor()
        """ Check if the tables we want are already represented in the database """
        try:
            cur.execute("SELECT * FROM t_data_cache")
        except sqlite3.OperationalError:
            return False

        return True

    """ Add data to the table """
    def add_data(self, data, source="UNKNOWN", timestamp=-1):
        if not self.dbconn:
            return False

        """ Identify our target table """
        table_name = "t_data_cache"

        """ Define our target fields """
        columns = "C_RETRIEVE_TIME, C_ORIGIN, C_DATA"

        """ Define the values to be inserted """
        if timestamp <= 0:
            timestamp = long(time.time())

        values = '%li, "%s", "%s"' % (timestamp, source, data)

        """ Build our INSERT query """
        query = "INSERT INTO %s (%s) VALUES (?, ?, ?);" % (table_name, columns)

        """ And execute it using our database connection """
        return self.perform(query, (long(timestamp), source, data))

    """ Retrieve data from our database """
    def get_data(self, limit=0, offset=0, cond=DEFAULT_GET_COND):
        if not self.dbconn:
            return False

        """ Identify our target table """
        table_name = "t_data_cache"

        """ Define our target fields """
        columns = "C_ID, C_ORIGIN, C_RETRIEVE_TIME, C_DATA"

        """ Build our SELECT query """
        query = "SELECT %s FROM %s WHERE %s" % (columns, table_name, cond)

        """ Set our offset """
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

    """ Flag data as uploaded """
    def set_data_uploaded(self, rec_id):
        if not self.dbconn:
            return False

        """ Define the parts of our UPDATE query """
        table_name = "t_data_cache"
        update = "C_UPLOAD_TIME = %li" % (long(time.time()))
        condition = "C_ID = %i" % (rec_id)

        """ Build our UPDATE query """
        query = "UPDATE %s SET %s WHERE %s" % (table_name, update, condition)

        """ And execute it using our database connection """
        return self.perform(query)

    """ Disconnect from the database """
    def disconnect(self):
        if self.dbconn == None:
            return
        self.dbconn.close()

    """ Execute the query using the provided database connection """
    def perform(self, query, extras=None):
        try:
            if extras == None:
                self.dbconn.execute(query)
            else:
                self.dbconn.execute(query, extras)

            self.dbconn.commit()
        except sqlite3.OperationalError:
            print("Query Failed: " + query)
            return False
        return True

