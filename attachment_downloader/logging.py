"""
Common logger functionality.
"""
import logging
import sys

LEVELS = ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL')
FORMAT = '%(asctime)s - %(levelname)s - %(message)s'


class Logger:
    """
    Logger utility class
    """
    @staticmethod
    def setup(level):
        """
        Log messages below WARNING to stdout, and WARNING and above to stderr.
        """
        std_out_stream_handler = logging.StreamHandler(sys.stdout)
        std_out_stream_handler.addFilter(lambda record: record.levelno < logging.WARNING)

        std_err_stream_handler = logging.StreamHandler(sys.stderr)
        std_err_stream_handler.setLevel(logging.WARNING)

        root_logger = logging.getLogger()
        root_logger.setLevel(level.upper())
        for handler in (std_out_stream_handler, std_err_stream_handler):
            handler.setFormatter(logging.Formatter(FORMAT))
            root_logger.addHandler(handler)
