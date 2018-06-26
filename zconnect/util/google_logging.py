import datetime
import logging
from logging import Formatter
import os


class GoogleFormatter(Formatter):

    """Logging Formatter which can be used to output logs to stderr in a format
    that can be parsed by google logging

    Note that any datefmt passed in to the setup will be ignored as this needs
    to be in a specific format to be recognised by google.
    """

    levels = {
        logging.DEBUG: "D",
        logging.INFO: "I",
        logging.CRITICAL: "C",
        logging.ERROR: "E",
        logging.WARNING: "W",
    }

    fmt = "{levelname:s}{asctime:s} {pid:d} {file:s}:{line:d}] {message:s}"

    def format(self, record):
        r"""Format for google stdout

        needs to match (ruby regex):

        `/^(?<severity>\w)(?<time>\d{4} [^\s]*)\s+(?<pid>\d+)\s+(?<source>[^ \]]+)\] (?<log>.*)/`

        precisely:

        https://github.com/google/glog/blob/master/src/glog/logging.h.in#L279-L301

        // Log lines have this form:
        //
        //     Lmmdd hh:mm:ss.uuuuuu threadid file:line] msg...
        //
        // where the fields are defined as follows:
        //
        //   L                A single character, representing the log level
        //                    (eg 'I' for INFO)
        //   mm               The month (zero padded; ie May is '05')
        //   dd               The day (zero padded)
        //   hh:mm:ss.uuuuuu  Time in hours, minutes and fractional seconds
        //   threadid         The space-padded thread ID as returned by GetTID()
        //                    (this matches the PID on Linux)
        //   file             The file name
        //   line             The line number
        //   msg              The user-supplied message
        //
        // Example:
        //
        //   I1103 11:57:31.739339 24395 google.cc:2341] Command line: ./some_prog
        //   I1103 11:57:31.739403 24395 google.cc:2342] Process id 24395
        """

        return self.fmt.format(
            levelname=self.levels[record.levelno],
            asctime=self.formatTime(record),
            pid=os.getpid(),
            file=record.module,
            line=record.lineno,
            message=record.getMessage(),
        )

    def formatTime(self, record, datefmt=None):
        """Format date as above

        datefmt is ignored
        """

        return datetime.datetime.fromtimestamp(record.created).strftime("%m%d %H:%M:%S.%f")
