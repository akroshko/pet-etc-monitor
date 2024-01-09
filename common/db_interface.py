#!/usr/bin/env python3
"""The functions used for the database interface.

For now I am not handling exceptions within this library, but instead
allowing the app itself to handle them and log them appropriately.

"""
from collections import namedtuple

import psycopg2
import psycopg2.pool
# TODO: remove next update?
# import psycopg2.sql
import psycopg2.extras

""" Stores information related to the current database. """
DBContext=namedtuple("DBContext",
                     ["connection",
                      "image_table"])
""" A named tuple of relevant items from the database. """
DBImageReturn=namedtuple("DBImageReturn",
                         ["image_uuid",
                          "image_valid",
                          "image_filename",
                          "image_end_time"])

""" A named tuple of log info from database. """
DBLogInfo=namedtuple("DBLogInfo",
                     ["image_uuid",
                      "image_valid",
                      "image_start_time",
                      "image_end_time",
                      "status_start_time",
                      "status_end_time"])

""" A class of the data recorded with each image. """
class RecordImageData():
    def __init__(self):
        self.next_image_uuid=None
        self.start_capture_time=None
        self.end_capture_time=None
        self.new_fullpath=None
        self.start_status_time=None
        self.end_status_time=None
        self.framesize_string=None
        self.image_valid=False
        self.image_width=None
        self.image_height=None

    def _as_tuple(self):
        return (self.next_image_uuid,
                self.start_capture_time,
                self.end_capture_time,
                self.new_fullpath,
                self.start_status_time,
                self.end_status_time,
                self.framesize_string,
                self.image_valid,
                self.image_width,
                self.image_height)

def db_get_connection(app_config,connection_pool):
    """ Get a connection to the database.

    @param app_config The config dictionary for the app.
    @param connection_pool The database connecton pool.
    @return A "DBContext" namedtuple.
    """
    image_table=app_config["POSTGRES_IMAGE_TABLE"]
    connection=connection_pool.getconn()
    return DBContext(connection,
                     image_table)

def db_release_connection(connection_pool,db_context):
    """ Release a connection to the database.

    @param connection_pool The database connecton pool.
    @param db_context A "DBContext" namedtuple.
    """
    connection_pool.putconn(db_context.connection)

def db_open_connection_pool(app_config):
    """ Open the database connection pool.

    @param app_config The config dictionary for the app.
    @return The database connection pool.
    """
    # set up psycopg2 for UUIDs
    psycopg2.extras.register_uuid()
    # check if database exists
    connection_pool=psycopg2.pool.ThreadedConnectionPool(6,18,
                                                         user=app_config["POSTGRES_USER"],
                                                         password=app_config["POSTGRES_PW"],
                                                         host=app_config["POSTGRES_HOSTNAME"],
                                                         port=app_config["POSTGRES_PORT"],
                                                         dbname=app_config["POSTGRES_DBNAME"])
    return connection_pool

def db_close_connection_pool(connection_pool):
    """ Close the database connection pool.

    @param connection_pool The database connecton pool.
    """
    if connection_pool:
        connection_pool.closeall()

def db_query_namedtuple(db_context,query_string,query_namedtuple,query_arguments):
    """
    """
    fields=query_namedtuple._fields
    fields_query=','.join(fields)
    query_string_actual=query_string.format(fields_query)
    with db_context.connection.cursor() as cursor:
        cursor.execute(query_string_actual,query_arguments)
        if cursor.rowcount > 0:
            db_result=cursor.fetchall()
        else:
            return []
        db_tuples=[]
        for row in db_result:
            if row != []:
                db_tuples.append(query_namedtuple._make(row))
    return db_tuples

def db_create_image_table(db_context,reset=False):
    """ Create the table of images.

    @param db_context A "DBContext" namedtuple.
    @param reset Drop any existing table first.

    """
    if reset:
        with db_context.connection.cursor() as cursor:
            cursor.execute("DROP TABLE IF EXISTS {};".format(db_context.image_table))
    # create the table if not exist
    query=("CREATE TABLE IF NOT EXISTS {} "
           "(image_uuid uuid PRIMARY KEY, "
           "image_start_time timestamp with time zone, "
           "image_end_time timestamp with time zone, "
           "image_filename VARCHAR (4096), "
           "status_start_time timestamp with time zone, "
           "status_end_time timestamp with time zone, "
           "status_framesize VARCHAR (4096), "
           "image_valid boolean, "
           "image_height integer, "
           "image_width integer "
           ");").format(db_context.image_table)
    with db_context.connection.cursor() as cursor:
        cursor.execute(query)
    db_context.connection.commit()

def db_insert_image(db_context,
                    record_image_data):
    """ Insert an image into the database.

    @param db_context A "DBContext" namedtuple.
    @param record_image_data
    """
    query=("INSERT INTO {} (image_uuid,image_start_time,image_end_time,image_filename,"
           "status_start_time,status_end_time,status_framesize,"
           "image_valid,image_height,image_width) "
           "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);").format(db_context.image_table)
    with db_context.connection.cursor() as cursor:
        cursor.execute(query,record_image_data._as_tuple())

def db_query_latest_image(db_context):
    """ Query the lastest image in the database.

    @param db_context A "DBContext" namedtuple.

    @return A "DBImageReturn" object.
    """
    # get latest image
    query_string=("SELECT {{}} FROM {} "
                  "WHERE image_valid=TRUE ORDER BY image_end_time DESC LIMIT 1;"
                  ).format(db_context.image_table)
    db_tuples=db_query_namedtuple(db_context,query_string,DBImageReturn,tuple())
    if db_tuples is not []:
        return DBImageReturn._make(db_tuples[0])
    else:
        return None

def db_query_past_image(db_context,before_time):
    """Query a past image in the database captured from before a
    particular time.

    @param db_context A "DBContext" namedtuple.
    @param before_time The time before which the image was captured.

    @return A "DBImageReturn" object.
    """
    query_string=("SELECT {{}} FROM {} "
                  "WHERE image_valid=TRUE and image_end_time <= %s ORDER BY image_end_time DESC LIMIT 1;"
                  ).format(db_context.image_table)
    db_tuples=db_query_namedtuple(db_context,query_string,DBImageReturn,(before_time,))
    if db_tuples is not []:
        return DBImageReturn._make(db_tuples[0])
    else:
        return None

def db_query_image_by_uuid(db_context,image_uuid):
    """Query an image based on it's uuid.

    @param db_context A "DBContext" namedtuple.
    @param image_uuid The uuid of the image.
    @return A filename corresponding to the image.
    """
    query_string=("SELECT image_filename FROM {} "
                  "WHERE image_uuid=%s;"
                  ).format(db_context.image_table)
    with db_context.connection.cursor() as cursor:
        cursor.execute(query_string,(image_uuid,))
        fetch=cursor.fetchone()
        image_filename=fetch[0]
    return image_filename

def db_query_image_logs(db_context):
    """Query the logs of the captured image.

    This is still very much a work in progress.

    @param db_context A "DBContext" namedtuple.
    @return A list of dictionaries corresponding to each image in the
    log.
    """
    query_string=("SELECT {{}} FROM {} "
                  "ORDER BY image_end_time ASC;").format(db_context.image_table)
    db_tuples=db_query_namedtuple(db_context,query_string,DBLogInfo,tuple())
    log_data=[tup._asdict() for tup in db_tuples]
    return log_data
