#!/opt/python-venv-global/venv-flask-test/bin/python3
"""The app that controls recording.

"""
import atexit
import json
import logging
import signal
import threading
import sys

import psycopg2

from flask import Flask

from common.utility import log_info_database,\
                           log_critical_configuration_exception,\
                           log_critical_unexpected_exception,\
                           log_critical_database_exception,\
                           log_critical_unexpected_exception

from common.db_interface import db_open_connection_pool,db_close_connection_pool

from record_background import RecordBackground,TERMINATE_EVENT
from record_app.routes import create_record_routes

DB_CONNECTION_POOL=None

APP_RUNNING=threading.Event()
APP_RUNNING.clear()
EXIT_CODE=0
RECORD_THREAD=None
DATABASE_OPEN=None
APP_ADDRESS=None
APP_PORT=None

def cleanup_app():
    """Stop the app itself."""
    logging.info("APP cleanup handler.")
    if APP_RUNNING.is_set():
        logging.info("APP cleanup handler raising signal.")
        signal.raise_signal(signal.SIGINT)
    else:
        logging.info("APP cleanup handler not raising signal.")
    logging.info("APP cleanup handler done.")

def cleanup_db():
    """Close the database."""
    logging.info("Database cleanup handler.")
    if DATABASE_OPEN:
        logging.info("Cleaning up database.")
        try:
            close_database_pool()
        except psycopg2.OperationalError as e:
            log_critical_database_exception(e)
        except Exception as e:
            log_critical_unexpected_exception(e)
        logging.info("Database cleanup handler done.")

def cleanup_background():
    """Close the background recording thread."""
    logging.info("Background thread cleanup handler.")
    if RECORD_THREAD:
        TERMINATE_EVENT.set()
        if RECORD_THREAD:
            logging.info("Waiting on join to background thread.")
            RECORD_THREAD.join()
        logging.info("Background thread cleanup handler done.")

def cleanup_handler():
    """Handle cleanup."""
    logging.info("Cleanup handler.")
    cleanup_background()
    cleanup_db()
    logging.info("Cleanup handler done.")

def signal_handler(*_,**__):
    """Handle cleanup from a signal."""
    logging.info("Cleanup signal.")
    cleanup_app()
    cleanup_handler()
    logging.info("Signal handler done.")

def open_database_pool(app_config):
    """Open the database pool for this app.

    @param app_config The config dictionary for the app.

    """
    global DB_CONNECTION_POOL
    log_info_database("Database connection pool opening...")
    DB_CONNECTION_POOL=db_open_connection_pool(app_config)
    log_info_database("Database connection pool opened")

def close_database_pool():
    """Close the database pool for this app."""
    log_info_database("Database connection pool closing...")
    db_close_connection_pool(DB_CONNECTION_POOL)
    log_info_database("Database connection pool closed")

def setup_background(app_config):
    """Setup the background recording task for the app."""
    database_pool=DB_CONNECTION_POOL
    try:
        # set up signal
        record_background_runnable=RecordBackground(app_config,DB_CONNECTION_POOL)
        record_thread=threading.Thread(target=record_background_runnable.run,
                                       args=[])
        if record_thread:
            record_thread.start()
    except Exception as e:
        logging.critical(e,exc_info=True)
        return
    return record_thread

def create_record_app(use_wsgi=False):
    """Called from the actual script that runs the app in order to
    create the app."""
    global EXIT_CODE
    global APP_ADDRESS
    global APP_PORT
    global DATABASE_OPEN
    global RECORD_THREAD
    atexit.register(cleanup_handler)
    signal.signal(signal.SIGTERM,signal_handler)
    # TODO: do I want to catch this
    # signal.signal(signal.SIGPIPE,signal_handler)
    signal.signal(signal.SIGHUP,signal_handler)
    if use_wsgi:
        config_filename="config_wsgi.json"
    else:
        config_filename="config_test.json"
    try:
        with open(config_filename,"r") as fh:
            app_config=json.load(fh)
    except OSError as e:
        log_critical_configuration_exception(e)
        EXIT_CODE=1
        return
    except Exception as e:
        log_critical_unexpected_exception(e)
        EXIT_CODE=1
        return
    #
    try:
        APP_ADDRESS=app_config["APP_RECORD_SERVE_ADDRESS"]
        APP_PORT=app_config["APP_RECORD_SERVE_PORT"]
        open_database_pool(app_config)
    except KeyError as e:
        log_critical_configuration_exception(e)
        EXIT_CODE=1
        return
    except psycopg2.OperationalError as e:
        log_critical_database_exception(e)
        EXIT_CODE=1
        return
    except Exception as e:
        log_critical_unexpected_exception(e)
        EXIT_CODE=1
        return
    DATABASE_OPEN=True
    RECORD_THREAD=setup_background(app_config)
    if not RECORD_THREAD:
        logging.critical("Unable to setup background recording.")
        TERMINATE_EVENT.set()
        EXIT_CODE=1
        return
    if TERMINATE_EVENT.is_set():
        EXIT_CODE=1
        return
    app = Flask(__name__)
    try:
        app.config.update(app_config)
    except KeyError as e:
        log_critical_configuration_exception(e)
        return
    except Exception as e:
        log_critical_unexpected_exception(e)
        return
    create_record_routes(app,app_config,
                         DB_CONNECTION_POOL)
    return app