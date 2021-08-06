
from datetime import datetime

import inspect

import logging

class Timer:
    def __init__(self, identifier, log=True):
        self.identifier = identifier
        self.logger_name = None
        self.start = None

    def __enter__(self):
        frm = inspect.stack()[1]
        mod = inspect.getmodule(frm[0])
        self.logger_name = mod.__name__

        self.start = datetime.now()
        return self

    def __exit__(self, exc_type, exc_value, trace):
        end = datetime.now()
        secs = (end - self.start).total_seconds()
        logger = logging.getLogger(self.logger_name)
        logger.info("time for '{}': {} s".format(self.identifier, secs))
        self.start = None
        self.logger_name = None


