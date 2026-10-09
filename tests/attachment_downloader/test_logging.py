import logging

import pytest
from assertpy import assert_that

from attachment_downloader.logging import Logger


@pytest.fixture(name='root_logger')
def root_logger_fixture():
    root_logger = logging.getLogger()
    handlers, level = root_logger.handlers[:], root_logger.level
    root_logger.handlers = []
    yield root_logger
    root_logger.handlers, root_logger.level = handlers, level


class TestLogger:
    def test_warnings_are_only_logged_to_stderr(self, root_logger, capsys):
        Logger.setup('INFO')
        root_logger.info('info message')
        root_logger.warning('warning message')

        captured = capsys.readouterr()
        assert_that(captured.out).contains('INFO - info message').does_not_contain('warning message')
        assert_that(captured.err).contains('WARNING - warning message').does_not_contain('info message')

    def test_log_level(self, root_logger, capsys):
        Logger.setup('debug')
        root_logger.debug('debug message')
        assert_that(capsys.readouterr().out).contains('DEBUG - debug message')

        root_logger.handlers = []
        Logger.setup('ERROR')
        root_logger.warning('warning message')
        assert_that(capsys.readouterr().err).is_empty()
