""" The routes for the record app.
"""

import uuid

from flask import redirect,url_for,\
                  send_from_directory,\
                  jsonify

from common.db_interface import db_get_connection,db_release_connection,\
                                db_query_image_logs

from record_background import CAPTURE_EVENT

DEBUG_UNIQUE_ID=str(uuid.uuid4())

def create_record_routes(app,app_config,
                         db_connection_pool):
    """ Create routes for the record app.
    """
    @app.route("/", methods=["GET"], strict_slashes=False)
    def index():
        """The default route."""
        return redirect(url_for("admin"))

    @app.route("/admin", methods=["GET"], strict_slashes=False)
    def admin():
        """The default route to control and monitor recording."""
        return send_from_directory("./templates","index_template.html")

    @app.route("/log", methods=["GET"], strict_slashes=False)
    def log():
        """The default route to control and monitor recording."""
        # db_query
        db_context=db_get_connection(app_config,db_connection_pool)
        # get a text file of logs from the past hour
        log_query=db_query_image_logs(db_context)
        db_release_connection(db_connection_pool,db_context)
        return jsonify(log_query)

    @app.route("/recording_status", methods=["GET"], strict_slashes=False)
    def get_recording_status():
        """Route to get the recording status.

        """
        is_capturing=CAPTURE_EVENT.is_set()
        if is_capturing:
            return "true"
        else:
            return "false"

    @app.route("/start_record", methods=["PUT"], strict_slashes=False)
    def start_record():
        """Route to start recording.

        """
        CAPTURE_EVENT.set()
        return "started with success"

    @app.route("/stop_record", methods=["PUT"], strict_slashes=False)
    def stop_record():
        """Route to stop recording.

        """
        CAPTURE_EVENT.clear()
        return "stopped with success"

    @app.route("/debug_uuid", methods=["GET"], strict_slashes=False)
    def get_debug_uuid():
        """For debugging purposes. Allows finding when the server has
        been restarted.

        """
        return DEBUG_UNIQUE_ID
