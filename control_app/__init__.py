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

import rpyc

from common.utility import log_info_database,\
                           log_critical_configuration_exception,\
                           log_critical_unexpected_exception,\
                           log_critical_database_exception,\
                           log_critical_unexpected_exception

from common.db_interface import db_open_connection_pool,db_close_connection_pool

from control_app.routes import create_control_routes

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
        # this sends the signal to flask app
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
        except psycopg2.OperationalError as err:
            log_critical_database_exception(err)
        except Exception as err:
            log_critical_unexpected_exception(err)
        logging.info("Database cleanup handler done.")

def cleanup_handler():
    """Handle cleanup."""
    logging.info("Cleanup handler.")
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

def create_control_app(config_filename=None):
    """Called from the actual script that runs the app in order to
    create the app."""
    global EXIT_CODE
    global APP_ADDRESS
    global APP_PORT
    global DATABASE_OPEN
    global RECORD_THREAD
    atexit.register(cleanup_handler)
    # disable signal handlers for WSGI
    try:
        with open(config_filename,"r") as fh:
            app_config=json.load(fh)
    except OSError as err:
        log_critical_configuration_exception(err)
        EXIT_CODE=1
        return
    except Exception as err:
        log_critical_unexpected_exception(err)
        EXIT_CODE=1
        return
    try:
        APP_ADDRESS=app_config["APP_RECORD_SERVE_ADDRESS"]
        APP_PORT=app_config["APP_RECORD_SERVE_PORT"]
        use_signals=app_config["APP_USE_SIGNALS"]
        open_database_pool(app_config)
    except KeyError as err:
        log_critical_configuration_exception(err)
        EXIT_CODE=1
        return
    except psycopg2.OperationalError as err:
        log_critical_database_exception(err)
        EXIT_CODE=1
        return
    except Exception as err:
        log_critical_unexpected_exception(err)
        EXIT_CODE=1
        return
    if use_signals:
        signal.signal(signal.SIGTERM,signal_handler)
        # do I want to catch this?
        # signal.signal(signal.SIGPIPE,signal_handler)
        signal.signal(signal.SIGHUP,signal_handler)
    DATABASE_OPEN=True
    app = Flask(__name__)
    try:
        app.config.update(app_config)
    except KeyError as err:
        log_critical_configuration_exception(err)
        return
    except Exception as err:
        log_critical_unexpected_exception(err)
        return
    create_control_routes(app,app_config,
                          DB_CONNECTION_POOL)
    return app
