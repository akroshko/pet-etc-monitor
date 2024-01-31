"""Utility functions that do not have a specific package.

"""
import datetime
import logging

LOGGING_FORMAT_STRING="%(levelname)s:%(asctime)s %(message)s"

_OS_ERROR_STRING="OS error"
_CONFIGURATION_ERROR_STRING="Configuration error"
_UNEXPECTED_ERROR_STRING="Unexpected error"
_DATABASE_ERROR_STRING="Database error"
_RECORDING_ERROR_STRING="Record error"
_IMAGEFILE_ERROR_STRING="Image file error"
_INVALID_USER_INPUT_ERROR_STRING="Invalid user input error"
_URL_ERROR_APP="Error connecting to another part of the app"

_DATABASE_INFO="Database info"

def log_critical_os_exception(e):
    """Log a critical exception related to an OSError.

    @param e The error message generated by the exception.

    """
    logging.critical(_build_error_string(_OS_ERROR_STRING,e),
                     exc_info=True)

def log_error_configuration_exception(e):
    """ Log an exception related to a configuration error.

    @param e The error message generated by the exception.
    """
    logging.error(_build_error_string(_CONFIGURATION_ERROR_STRING,e),
                  exc_info=True)

def log_critical_configuration_exception(e):
    """Log a critical exception related to a configuration error.

    @param e The error message generated by the exception.

    """
    logging.critical(_build_error_string(_CONFIGURATION_ERROR_STRING,e),
                     exc_info=True)

def log_error_unexpected_exception(e):
    """Log an exception that is unexpected or unhandled by other
    categories.

    @param e The error message generated by the exception.

    """
    logging.error(_build_error_string(_UNEXPECTED_ERROR_STRING,e),
                  exc_info=True)

def log_critical_unexpected_exception(e):
    """Log a critical exception that is unexpected or unhandled by other
    categories.

    @param e The error message generated by the exception.

    """
    logging.critical(_build_error_string(_UNEXPECTED_ERROR_STRING,e),
                     exc_info=True)

def log_error_database_exception(e):
    """Log an exception related to the database.

    @param e The error message generated by the exception.

    """
    logging.error(_build_error_string(_DATABASE_ERROR_STRING,e),
                  exc_info=True)

def log_error_app_url_exception(e):
    """Log an exception related to finding a url within app itself.

    @param e The error message generated by the exception.
    """
    logging.error(_build_error_string(_URL_ERROR_APP,e),
                  exc_info=True)

def log_critical_database_exception(e):
    """Log a critical exception related to the database.

    @param e The error message generated by the exception.

    """
    logging.critical(_build_error_string(_DATABASE_ERROR_STRING,e),
                     exc_info=True)

def log_error_recording_exception(e):
    """ Log an excepton related to recording.

    @param e The error message generated by the exception.
    """
    logging.error(_build_error_string(_RECORDING_ERROR_STRING,e),
                  exc_info=True)

def log_error_imagefile_exception(e):
    """ Log an excepton related to an imagefile.

    @param e The error message generated by the exception.
    """
    logging.error(_build_error_string(_IMAGEFILE_ERROR_STRING,e),
                  exc_info=True)

def log_error_invalid_user_input_exception(e):
    """ Log an excepton related to invalid user input.

    @param e The error message generated by the exception.
    """
    logging.error(_build_error_string(_INVALID_USER_INPUT_ERROR_STRING,e),
                  exc_info=True)

def log_info_database(message):
    """ Log info related to the database.
    """
    logging.info(_build_error_string(_DATABASE_INFO,message))

def _build_error_string(error_string,e):
    """

    @param error_string Additional context for the specific message.
    @param e The error message generated by the exception.
    """
    return "{}\n{}".format(error_string,e)

def get_time_now():
    """ Get the time in UTC now.
    """
    return datetime.datetime.now(datetime.timezone.utc)
