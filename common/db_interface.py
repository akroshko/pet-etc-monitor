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
                      "cursor",
                      "image_table"])
""" A named tuple of relevant items from the database. """
DBImageReturn=namedtuple("DBImageReturn",
                         ["image_valid",
                          "image_uuid",
                          "filename",
                          "image_end_time"])

def db_get_connection(app_config,connection_pool):
    """ Get a connection to the database.

    @param app_config The config dictionary for the app.
    @param connection_pool The database connecton pool.
    @return A "DBContext" namedtuple.
    """
    image_table=app_config["POSTGRES_IMAGE_TABLE"]
    connection=connection_pool.getconn()
    cursor=connection.cursor()
    return DBContext(connection,
                     cursor,
                     image_table)

def db_release_connection(connection_pool,db_context):
    """ Release a connection to the database.

    @param connection_pool The database connecton pool.
    @param db_context A "DBContext" namedtuple.
    """
    db_context.cursor.close()
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

def db_create_image_table(db_context,reset=False):
    """ Create the table of images.

    @param db_context A "DBContext" namedtuple.
    @param reset Drop any existing table first.

    """
    if reset:
        db_context.cursor.execute("DROP TABLE IF EXISTS {};".format(db_context.image_table))
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
    db_context.cursor.execute(query)
    db_context.connection.commit()

def db_insert_image(db_context,
                    next_image_uuid,start_capture_time,end_capture_time,
                    new_fullpath,start_status_time,end_status_time,framesize_string,
                    image_valid,image_height,image_width):
    """ Insert an image into the database.

    @param db_context A "DBContext" namedtuple.
    @param next_image_uuid
    @param start_capture_time
    @param end_capture_time
    @param new_fullpath
    @param start_status_time
    @param end_status_time
    @param framesize_string,
    @param image_valid
    @param image_height
    @param image_width

    """
    query=("INSERT INTO {} (image_uuid,image_start_time,image_end_time,image_filename,"
           "status_start_time,status_end_time,status_framesize,"
           "image_valid,image_height,image_width) "
           "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);").format(db_context.image_table)
    db_context.cursor.execute(query,(next_image_uuid,start_capture_time,end_capture_time,
                                     new_fullpath,start_status_time,end_status_time,framesize_string,
                                     image_valid,image_height,image_width))


def db_query_latest_image(db_context):
    """ Query the lastest image in the database.

    @param db_context A "DBContext" namedtuple.

    @return A "DBImageReturn" object.
    """
    # get latest image
    query=("SELECT image_uuid,image_filename,image_end_time FROM {} "
           "WHERE image_valid=TRUE ORDER BY image_end_time DESC LIMIT 1;"
           ).format(db_context.image_table)
    db_context.cursor.execute(query)
    fetch=db_context.cursor.fetchone()
    if fetch is not None:
        image_uuid=fetch[0]
        filename=fetch[1]
        image_end_time=fetch[2]
        return DBImageReturn(True,image_uuid,filename,image_end_time)
    else:
        return DBImageReturn(False,None,None,None)

def db_query_past_image(db_context,before_time):
    """Query a past image in the database captured from before a
    particular time.

    @param db_context A "DBContext" namedtuple.
    @param before_time The time before which the image was captured.

    @return A "DBImageReturn" object.
    """
    query=("SELECT image_uuid,image_filename,image_end_time FROM {} "
           "WHERE image_valid=TRUE and image_end_time <= %s ORDER BY image_end_time DESC LIMIT 1;"
           ).format(db_context.image_table)
    db_context.cursor.execute(query,(before_time,))
    fetch=db_context.cursor.fetchone()
    if fetch is not None:
        image_uuid=fetch[0]
        filename=fetch[1]
        image_end_time=fetch[2]
        return DBImageReturn(True,image_uuid,filename,image_end_time)
    else:
        return DBImageReturn(False,None,None,None)

def db_query_image_by_uuid(db_context,image_uuid):
    """Query an image based on it's uuid.

    @param db_context A "DBContext" namedtuple.
    @param image_uuid The uuid of the image.
    @return A filename corresponding to the image.
    """
    query=("SELECT image_filename FROM {} "
           "WHERE image_uuid=%s;"
           ).format(db_context.image_table)
    db_context.cursor.execute(query,(image_uuid,))
    fetch=db_context.cursor.fetchone()
    image_filename=fetch[0]
    return image_filename

def db_query_image_logs(db_context):
    """Query the logs of the captured image.

    This is still very much a work in progress.

    @param db_context A "DBContext" namedtuple.
    @return A list of dictionaries corresponding to each image in the
    log.
    """
    query=("SELECT image_uuid,image_valid,image_start_time,image_end_time,status_start_time,status_end_time FROM {} "
           "ORDER BY image_end_time ASC;").format(db_context.image_table)
    db_context.cursor.execute(query,)
    log_data=[]
    fetch=db_context.cursor.fetchall()
    for f in fetch:
        log_data_element={}
        log_data_element["image_uuid"]=f[0]
        log_data_element["image_valid"]=f[1]
        log_data_element["image_start_time"]=f[2]
        log_data_element["image_end_time"]=f[3]
        log_data_element["status_start_time"]=f[4]
        log_data_element["status_end_time"]=f[5]
        log_data.append(log_data_element)
    log_data.reverse()
    return log_data
