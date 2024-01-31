"""Record the camera in the background in a seperate thread.
"""
import argparse
import logging
import json
import os
import threading
import time
import sys
import urllib.request
import uuid

from PIL import Image
import psycopg2
import rpyc

from common.utility import get_time_now,\
                           log_critical_os_exception,\
                           log_error_unexpected_exception,\
                           log_error_database_exception,\
                           log_error_recording_exception,\
                           log_critical_database_exception,\
                           log_critical_unexpected_exception,\
                           log_error_imagefile_exception,\
                           log_critical_configuration_exception
from common.db_interface import db_create_image_table,\
                                db_insert_image,\
                                db_get_connection,\
                                db_release_connection,\
                                db_open_connection_pool,\
                                db_close_connection_pool,\
                                RecordImageData

from common.hardware import ESP32_FRAMESIZE

HELPSTRING=""
NON_CAPTURING_DELAY=1

class ProgramContext:
    def __init__(self):
        self.rpyc_server=None
        self.record_background=None
        # flag to indicate the program is terminating
        self.terminate_event=threading.Event()
        self.terminate_event.clear()

    def cleanup(self):
        self.terminate_event.set()
        if self.rpyc_server:
            self.rpyc_server.close()
        self.record_background.cleanup()

    def signal_handler(self,*_,**__):
        """Handle cleanup from a signal."""
        logging.info("Cleanup signal.")
        self.cleanup()
        logging.info("Signal handler done.")
PROGRAM_CONTEXT=ProgramContext()

class RecordBackgroundRPYC(rpyc.Service):
    """The RPC server for communicating with other parts of the application."""
    def __init__(self):
        rpyc.Service.__init__(self)

    def on_connect(self, conn):
        pass

    def on_disconnect(self, conn):
        pass

    def exposed_recording_status(self):
        """Check the recording status. """
        return PROGRAM_CONTEXT.record_background.capture_event.is_set()

    def exposed_start_recording(self):
        """Start the recording. """
        PROGRAM_CONTEXT.record_background.capture_event.set()

    def exposed_stop_recording(self):
        """Stop the recording. """
        PROGRAM_CONTEXT.record_background.capture_event.clear()

class RecordBackground():
    """Class to encapsulate the recording thread and database connection. """
    def __init__(self,app_config):
        """
        Setup the background recording task for the app.

        Args:
          app_config: Dictionary containing the application configuration.
        """
        self.record_thread=None
        # flag to indicate whether the program is capturing
        self.capture_event=threading.Event()
        self.capture_event.set()
        try:
            self._parser=self._init_arguments(sys.argv[1:])
            self._image_storage_path=app_config["IMAGE_STORAGE_PATH"]
            self._capture_url=app_config["CAPTURE_URL"]
            self._status_url=app_config["STATUS_URL"]
            if (temp:=app_config.get("RECORD_ROTATE")):
                self._record_rotate=int(temp)
            else:
                self._record_rotate=None
        except KeyError as err:
            log_critical_configuration_exception(err)
            self._terminate_unsuccessful()
            return
        except Exception as err:
            log_critical_unexpected_exception(err)
            self._terminate_unsuccessful()
            return
        try:
            self._db_connection_pool=db_open_connection_pool(app_config)
            self._db_context=db_get_connection(app_config,self._db_connection_pool)
        except Exception as err:
            log_critical_database_exception(err)
            self._terminate_unsuccessful()
            return
        try:
            record_thread=threading.Thread(target=self.run,
                                           args=[])
            self.record_thread=record_thread
            if record_thread:
                record_thread.start()
        except Exception as err:
            logging.critical(err,exc_info=True)
            return

    def _init_arguments(self, argv):
        parser = argparse.ArgumentParser(description=HELPSTRING,
                                         formatter_class=argparse.RawTextHelpFormatter)
        parser.add_argument("--dry-run",
                            action="store_true",
                            help="Just sets up the program and exits. For testing.")
        parser.add_argument("--reset-database",
                            action="store_true",
                            help="Drop database tables and rebuild them.")
        return parser.parse_args(argv)

    def cleanup(self):
        """Close the background recording thread. Close the database
        connection pool.

        Args:
            record_thread: The thread used for recording.

        """
        logging.info("Background thread cleanup handler.")
        if self.record_thread:
            logging.info("Waiting on join to background thread.")
            self.record_thread.join()
            self.record_thread=None
        logging.info("Background thread cleanup handler done.")
        self._cleanup_db_context()
        db_close_connection_pool(self._db_connection_pool)
        self._db_connection_pool=None

    def _cleanup_db_context(self):
        try:
            if self._db_context:
                db_release_connection(self._db_connection_pool,self._db_context)
                self._db_context=None
        except psycopg2.OperationalError as err:
            log_error_database_exception(err)
        except Exception as err:
            log_error_unexpected_exception(err)

    def _terminate_unsuccessful(self):
        PROGRAM_CONTEXT.terminate_event.set()

    def _log_capture(self,record_image_data):
        # log an image capture
        logging.info("Captured %s from %s to %s",
                     record_image_data.image_filename,
                     record_image_data.image_start_time,
                     record_image_data.image_end_time)

    def _create_image_filename(self,image_uuid):
        # create an image filename from a uuid
        return "{}.jpg".format(image_uuid)

    def _create_image_fullpath(self,new_filename):
        # create the full path for an image based on uuid
        return os.path.join(self._image_storage_path,new_filename)

    def run(self):
        """Run the background recording until terminated."""
        # this is for simple and quick tests without capturing any images
        if self._parser.dry_run:
            return
        if not self._run_create_image_storage_path():
            self._terminate_unsuccessful()
            return
        if not self._run_init_reset_database():
            self._terminate_unsuccessful()
            return
        try:
            # start capturing images
            while not PROGRAM_CONTEXT.terminate_event.is_set():
                continue_loop=True
                is_capturing=self.capture_event.is_set()
                if not is_capturing:
                    time.sleep(NON_CAPTURING_DELAY)
                    continue
                # setup initial values to be inserted into DB
                # generally None or False until things get filled out
                record_image_data=RecordImageData()
                record_image_data.image_uuid=uuid.uuid4()
                record_image_data.image_start_time=get_time_now()
                # these don't involve any actual file operations
                record_image_data.image_filename=self._create_image_fullpath(
                    self._create_image_filename(
                        record_image_data.image_uuid))
                # capture the actual image
                continue_loop = continue_loop and self._run_capture_image(record_image_data)
                if not continue_loop:
                    continue
                # capture the actual image
                record_image_data.image_end_time=get_time_now()
                self._log_capture(record_image_data)
                record_image_data.status_start_time=get_time_now()
                continue_loop=continue_loop and self._run_capture_status(record_image_data)
                if not continue_loop:
                    continue
                # check image
                # right now I still record invalid images into the database
                self._run_verify_image(record_image_data)
                # for now failure to connect to db will kill the program
                # since this is usually a configuration error
                try:
                    db_insert_image(self._db_context,
                                    record_image_data)
                    self._db_context.connection.commit()
                except psycopg2.OperationalError as err:
                    log_error_database_exception(err)
                except Exception as err:
                    log_error_recording_exception(err)
        except Exception as err:
            log_error_unexpected_exception(err)
        print("Terminating background thread")

    # component functions of run
    def _run_create_image_storage_path(self):
        """Create the location to store the images."""
        try:
            if not os.path.exists(self._image_storage_path):
                os.makedirs(self._image_storage_path,exist_ok=True)
            return True
        except OSError as err:
            log_critical_os_exception(err)
            return None
        except Exception as err:
            log_critical_unexpected_exception(err)
            return None

    def _run_init_reset_database(self):
        """Initialize and optionally reset the database."""
        # drop old table if needed
        reset=bool(self._parser.reset_database)
        # database is setup here
        try:
            db_create_image_table(self._db_context,reset=reset)
            return True
        except psycopg2.OperationalError as err:
            log_critical_database_exception(err)
            return None
        except Exception as err:
            log_critical_unexpected_exception(err)
            return None

    def _run_capture_image(self,record_image_data):
        """Try and capture an image from the recording device.

        Args:
          record_image_data: A RecordImageData structure to record the image filename to.

        Returns:
          True if image captured successfully. None otherwise.
        """
        try:
            # capture the actual image
            with urllib.request.urlopen(
                    self._capture_url.format(
                        str(record_image_data.image_uuid)),
                    timeout=60) as response:
                with open(record_image_data.image_filename,'wb') as f:
                    f.write(response.read())
            return True
        except TimeoutError as err:
            log_error_recording_exception(err)
            return None
        except urllib.error.URLError as err:
            log_error_recording_exception(err)
            return None
        except (IOError,OSError) as err:
            log_error_imagefile_exception(err)
            return None
        except Exception as err:
            log_error_unexpected_exception(err)
            return None

    def _run_capture_status(self,record_image_data):
        """Try and capture a status from the recording device.

        Args:
          record_image_data: A RecordImageData structure to capture the status to.

        Returns:
          True if status captured successfully. None otherwise.
        """
        try:
            with urllib.request.urlopen(self._status_url) as f:
                record_image_data.status_end_time=get_time_now()
                # TODO check for invalid
                status_dict=json.load(f)
                # TODO: check for invalid
                framesize_number=status_dict["framesize"]
                record_image_data.status_framesize=ESP32_FRAMESIZE[framesize_number]
            return True
        except TimeoutError as err:
            log_error_recording_exception(err)
            return None
        except urllib.error.URLError as err:
            log_error_recording_exception(err)
            return None
        except (IOError,OSError) as err:
            log_error_imagefile_exception(err)
            return None
        except Exception as err:
            log_error_unexpected_exception(err)
            return None

    def _run_verify_image(self,record_image_data):
        """Verify a recorded image exists and is valid.

        Args:
          record_image_data: A RecordImageData structure that contains
          the data on the image to be verified.

        Returns:
          True if image exists and is valid. None otherwise.
        """
        try:
            with Image.open(record_image_data.image_filename,mode="r") as image:
                image.verify()
                # get width and height
                record_image_data.image_width=image.width
                record_image_data.image_height=image.height
                record_image_data.image_valid=True
            if self._record_rotate:
                image=Image.open(record_image_data.image_filename)
                image=image.rotate(angle=self._record_rotate,
                                   expand=True)
                image.save(record_image_data.image_filename)
            return True
        except (IOError,OSError) as err:
            log_error_imagefile_exception(err)
            record_image_data.image_valid=False
            return
        except Exception as err:
            log_error_unexpected_exception(err)
            record_image_data.image_valid=False
            return
        return True
