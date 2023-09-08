#!/opt/python-venv-global/venv-flask-test/bin/python3
"""A Flask App to record in a background thread from an ESP32 CAM (or
it's many clones).

See http://www.ai-thinker.com/pro_view-24.html for the original.

"""

import logging
import sys

from common.utility import LOGGING_FORMAT_STRING
import record_app
from record_background import TERMINATE_EVENT

logging.basicConfig(format=LOGGING_FORMAT_STRING,
                    level=logging.INFO)

if __name__ == "__main__":
    app=record_app.create_record_app()
    if not app:
        logging.critical("Unable to create recording app.")
        TERMINATE_EVENT.set()
        sys.exit(record_app.EXIT_CODE)
    else:
        record_app.APP_RUNNING.set()
        app.run(host=record_app.APP_ADDRESS,
                port=record_app.APP_PORT)
        record_app.APP_RUNNING.clear()
        TERMINATE_EVENT.set()
        sys.exit(record_app.EXIT_CODE)
