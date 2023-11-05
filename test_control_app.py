#!/usr/bin/env python3
"""Executable script to run the control_app Flask app.
"""

import logging
import sys

from common.utility import LOGGING_FORMAT_STRING
import control_app

logging.basicConfig(format=LOGGING_FORMAT_STRING,
                    level=logging.INFO)

if __name__ == "__main__":
    app=control_app.create_control_app()
    if not app:
        logging.critical("Unable to create recording app.")
        sys.exit(control_app.EXIT_CODE)
    else:
        control_app.APP_RUNNING.set()
        app.run(host=control_app.APP_ADDRESS,
                port=control_app.APP_PORT)
        control_app.APP_RUNNING.clear()
        sys.exit(control_app.EXIT_CODE)
