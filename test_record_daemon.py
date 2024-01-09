#!/usr/bin/env python3
"""Executable script to run the record_daemon and record an ESP32 CAM
(or it's many clones).

See http://www.ai-thinker.com/pro_view-24.html for the original.

"""
import atexit
import json
import logging
import os
import signal
import sys
import threading
import time

import rpyc

from common.db_interface import db_open_connection_pool,db_close_connection_pool
from common.utility import log_critical_configuration_exception,\
                           log_critical_unexpected_exception,\
                           LOGGING_FORMAT_STRING
from record_daemon import RecordBackground,\
                          TERMINATE_EVENT,\
                          CAPTURE_EVENT,\
                          cleanup_handler,\
                          signal_handler,\
                          setup_background,\
                          RecordBackgroundRPYC

logging.basicConfig(format=LOGGING_FORMAT_STRING,
                    level=logging.INFO)

if __name__ == '__main__':
    # open config first
    if '--use-wsgi' in sys.argv:
        config_filename="config_wsgi.json"
    else:
        config_filename="config_test.json"
    try:
        with open(config_filename,"r") as fh:
            app_config=json.load(fh)
        rpyc_port=app_config["RPYC_PORT"]
    except OSError as e:
        log_critical_configuration_exception(e)
        EXIT_CODE=1
        sys.exit(EXIT_CODE)
    except Exception as e:
        log_critical_unexpected_exception(e)
        EXIT_CODE=1
        sys.exit(EXIT_CODE)
    atexit.register(cleanup_handler)
    signal.signal(signal.SIGTERM,signal_handler)
    signal.signal(signal.SIGHUP,signal_handler)
    # TODO: catch this signal but ensure helper scripts still work
    # signal.signal(signal.SIGINT,signal_handler)
    # start up thread to record and DB
    RECORD_THREAD=setup_background(app_config)
    if not RECORD_THREAD:
        logging.critical("Unable to setup background recording.")
        TERMINATE_EVENT.set()
        EXIT_CODE=1
        sys.exit(EXIT_CODE)
    if TERMINATE_EVENT.is_set():
        EXIT_CODE=1
        sys.exit(EXIT_CODE)
    # start up rpyc server
    from rpyc.utils.server import ThreadedServer
    RPYC_SERVER = ThreadedServer(RecordBackgroundRPYC, port=rpyc_port, listener_timeout=120)
    RPYC_SERVER.start()
    cleanup_handler()
