#!/opt/python-venv-global/venv-flask-test/bin/python3
"""Executable to run script to run the view_app Flask app.
"""

import logging
import sys

from common.utility import LOGGING_FORMAT_STRING
import view_app

logging.basicConfig(format=LOGGING_FORMAT_STRING,
                    level=logging.INFO)

if __name__ == "__main__":
    app=view_app.create_view_app()
    if not app:
        logging.critical("Unable to create view app")
        sys.exit(1)
    else:
        view_app.APP_RUNNING.set()
        app.run(host=view_app.APP_ADDRESS,
                port=view_app.APP_PORT)
        view_app.APP_RUNNING.clear()
        sys.exit(0)
