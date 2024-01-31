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

from rpyc.utils.server import ThreadedServer

from common.utility import log_critical_configuration_exception,\
                           log_critical_unexpected_exception,\
                           LOGGING_FORMAT_STRING
from record_daemon import PROGRAM_CONTEXT,\
                          RecordBackground,\
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
    except OSError as err:
        log_critical_configuration_exception(err)
        EXIT_CODE=1
        sys.exit(EXIT_CODE)
    except Exception as err:
        log_critical_unexpected_exception(err)
        EXIT_CODE=1
        sys.exit(EXIT_CODE)
    atexit.register(PROGRAM_CONTEXT.cleanup)
    signal.signal(signal.SIGTERM,PROGRAM_CONTEXT.signal_handler)
    signal.signal(signal.SIGHUP,PROGRAM_CONTEXT.signal_handler)
    # TODO: catch this signal but ensure helper scripts still work
    # signal.signal(signal.SIGINT,RecordBackground.signal_handler)
    # start up thread to record and DB
    PROGRAM_CONTEXT.record_background=RecordBackground(app_config)
    if not PROGRAM_CONTEXT.record_background.record_thread:
        logging.critical("Unable to setup background recording.")
        PROGRAM_CONTEXT.terminate_event.set()
        EXIT_CODE=1
        sys.exit(EXIT_CODE)
    if PROGRAM_CONTEXT.terminate_event.is_set():
        EXIT_CODE=1
        sys.exit(EXIT_CODE)
    # start up rpyc server
    RPYC_SERVER = ThreadedServer(RecordBackgroundRPYC, port=rpyc_port, listener_timeout=120)
    RPYC_SERVER.start()
    PROGRAM_CONTEXT.cleanup()
