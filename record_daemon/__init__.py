#!/usr/bin/env python3
"""Record the camera in the background in a seperate thread.
"""
import argparse
import logging
import json
import os
import threading
import time
import sys
import uuid
import urllib.request

from PIL import Image
import psycopg2
import rpyc

# db_connect,db_close,
from common.utility import get_time_now,log_critical_os_exception,log_error_unexpected_exception,\
                           log_error_database_exception,log_error_recording_exception,\
                           log_critical_database_exception,log_critical_unexpected_exception,\
                           log_error_imagefile_exception, log_critical_configuration_exception
from common.db_interface import db_create_image_table,db_insert_image,\
                                db_get_connection,db_release_connection,\
                                db_open_connection_pool,db_close_connection_pool,\
                                RecordImageData

from common.hardware import ESP32_FRAMESIZE

HELPSTRING=""
NON_CAPTURING_DELAY=1

# flag initially false
TERMINATE_EVENT=threading.Event()
TERMINATE_EVENT.clear()
CAPTURE_EVENT=threading.Event()
CAPTURE_EVENT.set()

DB_CONNECTION_POOL=None
RECORD_THREAD=None
RPYC_SERVER=None

def cleanup_handler():
    """Handle cleanup."""
    logging.info("Cleanup handler.")
    if RPYC_SERVER:
        RPYC_SERVER.close()
    cleanup_background(RECORD_THREAD)
    logging.info("Cleanup handler done.")

def signal_handler(*_,**__):
    """Handle cleanup from a signal."""
    logging.info("Cleanup signal.")
    cleanup_handler()
    logging.info("Signal handler done.")

def setup_background(app_config):
    """Setup the background recording task for the app."""
    global DB_CONNECTION_POOL
    DB_CONNECTION_POOL=db_open_connection_pool(app_config)
    if DB_CONNECTION_POOL:
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
    else:
        return None

def cleanup_background(record_thread):
    """Close the background recording thread."""
    logging.info("Background thread cleanup handler.")
    TERMINATE_EVENT.set()
    if record_thread:
        logging.info("Waiting on join to background thread.")
        record_thread.join()
    logging.info("Background thread cleanup handler done.")
    db_close_connection_pool(DB_CONNECTION_POOL)

class RecordBackgroundRPYC(rpyc.Service):
    """ The RPC server. """
    def __init__(self):
        rpyc.Service.__init__(self)

    def on_connect(self, conn):
        pass

    def on_disconnect(self, conn):
        pass

    def exposed_recording_status(self):
        """ Check the recording status.
        """
        return CAPTURE_EVENT.is_set()

    def exposed_start_recording(self):
        """ Start the recording.
        """
        CAPTURE_EVENT.set()

    def exposed_stop_recording(self):
        """ Stop the recording.
        """
        CAPTURE_EVENT.clear()

class RecordBackground():
    """Class to encompass all things needed for background recording.
    """
    def __init__(self,app_config,db_connection_pool):
        if TERMINATE_EVENT.is_set():
            return
        try:
            self._db_connection_pool=db_connection_pool
            self._db_context=db_get_connection(app_config,db_connection_pool)
        except Exception as e:
            log_critical_database_exception(e)
            self._terminate_unsuccessful()
        try:
            self._parser=self._setup_arguments(sys.argv[1:])
            self._image_storage_path=app_config["IMAGE_STORAGE_PATH"]
            self._capture_url=app_config["CAPTURE_URL"]
            self._status_url=app_config["STATUS_URL"]
            if "RECORD_ROTATE" in app_config:
                self._record_rotate=int(app_config["RECORD_ROTATE"])
            else:
                self._record_rotate=None
        except KeyError as e:
            log_critical_configuration_exception(e)
            self._terminate_unsuccessful()
        except Exception as e:
            log_critical_unexpected_exception(e)
            self._terminate_unsuccessful()
        self._has_failed=False

    def _get_db_context(self):
        return self._db_context

    def _cleanup_db(self):
        try:
            db_release_connection(self._db_connection_pool,self._db_context)
        except psycopg2.OperationalError as e:
            log_error_database_exception(e)
        except Exception as e:
            log_error_unexpected_exception(e)

    def _setup_arguments(self, argv):
        parser = argparse.ArgumentParser(description=HELPSTRING,
                                         formatter_class=argparse.RawTextHelpFormatter)
        parser.add_argument("--test",
                            action="store_true",
                            help="Just sets up the program and exits. For testing.")
        parser.add_argument("--reset-database",
                            action="store_true",
                            help="Drop database tables and rebuild them.")
        return parser.parse_args(argv)

    def _terminate_unsuccessful(self):
        TERMINATE_EVENT.set()

    def _log_capture(self,new_fullpath,start_capture_time,end_capture_time):
        # log an image capture
        logging.info("Captured {} from {} to {}".format(new_fullpath,start_capture_time,end_capture_time))

    def _create_image_filename(self,image_uuid):
        # create an image filename from a uuid
        return "{}.jpg".format(image_uuid)

    def _create_image_fullpath(self,new_filename):
        # create the full path for an image based on uuid
        return os.path.join(self._image_storage_path,new_filename)

    # component functions of run
    def _run_create_image_storage_path(self):
        try:
            if not os.path.exists(self._image_storage_path):
                os.makedirs(self._image_storage_path,exist_ok=True)
        except OSError as e:
            log_critical_os_exception(e)
            self._has_failed=True
            return
        except Exception as e:
            log_critical_unexpected_exception(e)
            self._has_failed=True
            return

    def _run_init_reset_database(self):
        # drop old table if needed
        reset=bool(self._parser.reset_database)
        # database is setup here
        try:
            db_create_image_table(self._get_db_context(),reset=reset)
        except psycopg2.OperationalError as e:
            log_critical_database_exception(e)
            self._has_failed=True
            return
        except Exception as e:
            log_critical_unexpected_exception(e)
            self._has_failed=True
            return

    def _run_capture_image(self,record_image_data):
        try:
            # capture the actual image
            with urllib.request.urlopen(
                    self._capture_url.format(
                        str(record_image_data.next_image_uuid)),
                    timeout=60) as response:
                with open(record_image_data.new_fullpath,'wb') as f:
                    f.write(response.read())
            return True
        except TimeoutError as e:
            log_error_recording_exception(e)
            return False
        except urllib.error.URLError as e:
            log_error_recording_exception(e)
            return False
        except (IOError,OSError) as e:
            log_error_imagefile_exception(e)
            return False
        except Exception as e:
            log_error_unexpected_exception(e)
            return False

    def _run_capture_status(self,record_image_data):
        try:
            with urllib.request.urlopen(self._status_url) as f:
                record_image_data.end_status_time=get_time_now()
                # TODO check for invalid
                status_dict=json.load(f)
                # TODO: check for invalid
                framesize_number=status_dict["framesize"]
                record_image_data.framesize_string=ESP32_FRAMESIZE[framesize_number]
            return True
        except TimeoutError as e:
            log_error_recording_exception(e)
            return False
        except urllib.error.URLError as e:
            log_error_recording_exception(e)
            return False
        except (IOError,OSError) as e:
            log_error_imagefile_exception(e)
            return False
        except Exception as e:
            log_error_unexpected_exception(e)
            return False

    def _run_verify_image(self,record_image_data):
        # check image
        image_valid=None
        image_width=None
        image_height=None
        try:
            with Image.open(record_image_data.new_fullpath,mode="r") as image:
                image.verify()
                # get width and height
                record_image_data.image_width=image.width
                record_image_data.image_height=image.height
                record_image_data.image_valid=True
            if self._record_rotate:
                image=Image.open(record_image_data.new_fullpath)
                image=image.rotate(angle=self._record_rotate,
                                   expand=True)
                image.save(record_image_data.new_fullpath)
            return True
        except (IOError,OSError) as e:
            log_error_imagefile_exception(e)
            record_image_data.image_valid=False
        except Exception as e:
            log_error_unexpected_exception(e)
            record_image_data.image_valid=False
        return True

    def run(self):
        """ Run the background recording until terminated.
        """
        # this is for simple and quick tests
        if self._parser.test:
            return
        self._run_create_image_storage_path()
        if self._has_failed:
            self._terminate_unsuccessful()
            return
        self._run_init_reset_database()
        if self._has_failed:
            self._terminate_unsuccessful()
            self._cleanup_db()
            return
        try:
            # start capturing images
            while not TERMINATE_EVENT.is_set():
                continue_loop=True
                is_capturing=CAPTURE_EVENT.is_set()
                if not is_capturing:
                    time.sleep(NON_CAPTURING_DELAY)
                    continue
                # setup initial values to be inserted into DB
                # generally None or False until things get filled out
                record_image_data=RecordImageData()
                record_image_data.next_image_uuid=uuid.uuid4()
                record_image_data.start_capture_time=get_time_now()
                # these don't involve any actual file operations
                record_image_data.new_fullpath=self._create_image_fullpath(
                    self._create_image_filename(
                        record_image_data.next_image_uuid))
                # capture the actual image
                continue_loop = continue_loop and self._run_capture_image(record_image_data)
                if not continue_loop:
                    continue
                # capture the actual image
                record_image_data.end_capture_time=get_time_now()
                self._log_capture(record_image_data.new_fullpath,
                                  record_image_data.start_capture_time,
                                  record_image_data.end_capture_time)
                record_image_data.start_status_time=get_time_now()
                continue_loop=continue_loop and self._run_capture_status(record_image_data)
                if not continue_loop:
                    continue
                # check image
                # right now I still record invalid images
                self._run_verify_image(record_image_data)
                # for now failure to connect to db will kill the program
                # since this is usually a configuration error
                try:
                    db_insert_image(self._get_db_context(),
                                    record_image_data)
                    self._get_db_context().connection.commit()
                except psycopg2.OperationalError as e:
                    log_error_database_exception(e)
                except Exception as e:
                    log_error_recording_exception(e)
        except Exception as e:
            log_error_unexpected_exception(e)
        self._cleanup_db()
        print("Terminating background thread")
