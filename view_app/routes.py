""" The routes for the view app. """
import datetime
import json
import uuid
import urllib.request

from flask import send_file, send_from_directory, \
                  request,jsonify,redirect

from common.utility import get_time_now,\
                           log_error_configuration_exception,\
                           log_error_unexpected_exception,\
                           log_error_invalid_user_input_exception,\
                           log_error_app_url_exception
from common.db_interface import db_get_connection,db_release_connection,\
                                db_query_latest_image,\
                                db_query_past_image,\
                                db_query_image_by_uuid

DEBUG_UNIQUE_ID=str(uuid.uuid4())

def get_record_base_url(app_config):
    """Get the base url for accessing the record app.

    @param app_config

    @return
    """
    return "http://{}:{}/{}".format(app_config["APP_RECORD_CLIENT_HOST"],
                             str(app_config["APP_RECORD_CLIENT_PORT"]),
                             app_config["APP_RECORD_CLIENT_PATH"])

def get_recording_status_url(app_config):
    """Get the url for getting the recording status.

    @param app_config

    @return
    """
    base_url=get_record_base_url(app_config)
    record_url="{}/recording_status".format(base_url)
    return record_url

def get_admin_url(app_config):
    """Get the url for for the admin page of the recording app.

    @param app_config

    @return
    """
    base_url=get_record_base_url(app_config)
    admin_url="{}".format(base_url)
    return admin_url

def get_log_url(app_config):
    """Get the url for for the log page of the recording app.

    @param app_config

    @return
    """
    base_url=get_record_base_url(app_config)
    log_url="{}/log".format(base_url)
    return log_url

def create_view_routes(app,app_config,
                       db_connection_pool):
    """ Create routes for the view app.

    @param app_config
    @param db_connection_pool

    @return
    """
    @app.route("/", methods=["GET"])
    def index():
        """
        """
        return send_from_directory("./templates","index_template.html")

    @app.route("/current", methods=["POST"], strict_slashes=False)
    def current_image():
        """Get the latest image.

        This gets whatever is the most recent image in the database.

        @return JSON
                {
                 "image_valid":...,
                 "image_url":...,
                 "image_uuid":...,
                 "image_time":...
                 }

        @return
        """
        # db_query
        db_context=db_get_connection(app_config,db_connection_pool)
        try:
            db_query_result=db_query_latest_image(db_context)
        except Exception as err:
            log_error_unexpected_exception(err)
        db_release_connection(db_connection_pool,db_context)
        jsonified_dict=_create_json_return(db_query_result)
        return jsonified_dict

    @app.route("/past", methods=["POST"], strict_slashes=False)
    def past_image():
        """Get an image from the past.

        The "seconds_ago" parameter gives the minimum number of seconds in
        the past.

        @return JSON
                {
                 "image_valid":...,
                 "image_url":...,
                 "image_uuid":...,
                 "image_time":...
                 }

        @return
        """
        try:
            # seconds_ago = int(request.args.get("seconds_ago", None))
            seconds_ago=int(request.form["seconds_ago"])
        except ValueError as err:
            log_error_invalid_user_input_exception(err)
            return
        time_now=get_time_now()
        seconds_ago=datetime.timedelta(seconds=seconds_ago)
        before_time=time_now-seconds_ago
        # db query
        db_context=db_get_connection(app.config,db_connection_pool)
        try:
            db_query_result=db_query_past_image(db_context,before_time)
        except Exception as err:
            log_error_unexpected_exception(err)
            db_release_connection(db_connection_pool,db_context)
            return
        db_release_connection(db_connection_pool,db_context)
        jsonified_dict=_create_json_return(db_query_result)
        return jsonified_dict

    @app.route("/image", methods=["GET"], strict_slashes=False)
    def get_image():
        """Get a specific image.

        The "image_uuid" parameter gives the uuid of the image to get.

        @return The file corresponding to the image.
        """
        image_uuid = request.args.get("image_uuid", None)
        try:
            # throws a ValueError in case of an invalid UUID
            uuid.UUID(image_uuid,version=4)
        except ValueError as err:
            log_error_invalid_user_input_exception(err)
            return
        db_context=db_get_connection(app.config,db_connection_pool)
        try:
            image_filename=db_query_image_by_uuid(db_context,image_uuid)
        except Exception as err:
            log_error_unexpected_exception(err)
        db_release_connection(db_connection_pool,db_context)
        return send_file(image_filename)

    @app.route("/empty_image", methods=["POST"], strict_slashes=False)
    def get_empty_image():
        """Get an empty image.

        @return The file corresponding to the empty image.
        """
        return send_from_directory("./static","empty_1x1.png")

    @app.route("/admin", methods=["GET"], strict_slashes=False)
    def get_redirect_admin():
        """Get the admin page, expecting a redirection.

        @return
        """
        try:
            admin_url=get_admin_url(app_config)
            return redirect(admin_url, code=302)
        except KeyError as err:
            log_error_configuration_exception(err)
            return
        except Exception as err:
            log_error_unexpected_exception(err)
            return

    @app.route("/log", methods=["GET"], strict_slashes=False)
    def get_log():
        """Get the log page, expecting a redirection.

        @return
        """
        try:
            log_url=get_log_url(app_config)
        except KeyError as err:
            log_error_configuration_exception(err)
            return
        except Exception as err:
            log_error_unexpected_exception(err)
            return
        try:
            with urllib.request.urlopen(log_url) as response:
                response_dict=json.load(response)
        except urllib.error.URLError as err:
            log_error_app_url_exception(err)
            return
        except Exception as err:
            log_error_unexpected_exception(err)
            return
        return jsonify(response_dict)

    @app.route("/recording_status",methods=["GET"], strict_slashes=False)
    def get_recording_status():
        """Get the recording status.

        @return JSON {"status":...}
        """
        try:
            record_url=get_recording_status_url(app_config)
        except KeyError as err:
            log_error_configuration_exception(err)
            return
        except Exception as err:
            log_error_unexpected_exception(err)
            return
        # now fetch the record status
        try:
            with urllib.request.urlopen(record_url) as response:
                response_text=response.read()
        except urllib.error.URLError as err:
            log_error_app_url_exception(err)
            return
        except Exception as err:
            log_error_unexpected_exception(err)
            return
        response_dict={"status":None}
        try:
            # TODO: hate this b"true"
            if response_text==b"true":
                response_dict["status"]=True
            else:
                response_dict["status"]=False
        except Exception as err:
            log_error_unexpected_exception(err)
        return jsonify(**response_dict)

    @app.route("/debug_uuid", methods=["GET"], strict_slashes=False)
    def get_debug_uuid():
        """For debugging purposes. Allows finding when the server has
        been restarted.

        @return
        """
        return DEBUG_UNIQUE_ID

    def _create_json_return(db_query_result):
        """Create the json data on an image from a "DBImageReturn"
        named tuple.

        @return JSON
                {
                 "image_valid":...,
                 "image_url":...,
                 "image_uuid":...,
                 "image_time":...
                 }
        """
        if db_query_result is None:
            image_valid=None
            image_uuid=None
            filename=None
            image_end_time=None
        else:
            image_valid=db_query_result.image_valid
            image_uuid=db_query_result.image_uuid
            filename=db_query_result.image_filename
            image_end_time=db_query_result.image_end_time
            if image_end_time:
                image_end_time=image_end_time.isoformat()
            if image_uuid:
                image_url="/image?image_uuid={}".format(image_uuid)
            else:
                image_url="/empty_image"
        json_dict={"image_valid":image_valid,
                   "image_url":image_url,
                   "image_uuid":filename,
                   "image_time":image_end_time}
        return jsonify(**json_dict)
