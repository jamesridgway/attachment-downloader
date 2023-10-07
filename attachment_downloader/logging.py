import logging
import sys


class Logger:
    @staticmethod
    def setup(level):
        std_out_stream_handler = logging.StreamHandler(sys.stdout)
        std_out_stream_handler.setLevel(logging.getLevelName(level))
        std_out_stream_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

        std_err_stream_handler = logging.StreamHandler(sys.stderr)
        std_err_stream_handler.setLevel(logging.WARNING)
        std_err_stream_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        root_logger.addHandler(std_out_stream_handler)
        root_logger.addHandler(std_err_stream_handler)
