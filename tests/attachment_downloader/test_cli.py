import datetime

import pytz as pytz
from assertpy import assert_that

from attachment_downloader.cli import valid_date


class TestCli:
    def test_valid_date(self):
        assert_that(valid_date(None, '--date-after', '2022-03-03T13:00:00'))\
            .is_equal_to(pytz.utc.localize(datetime.datetime(2022, 3, 3, 13, 0, 0, 0)))

        assert_that(valid_date(None, '--date-after', '2022-03-03T13:00:00Z')) \
            .is_equal_to(pytz.utc.localize(datetime.datetime(2022, 3, 3, 13, 0, 0, 0)))

        assert_that(valid_date(None, '--date-after', '2022-03-03T13:00:00+00:00')) \
            .is_equal_to(pytz.utc.localize(datetime.datetime(2022, 3, 3, 13, 0, 0, 0)))

        assert_that(valid_date(None, '--date-after', '2022-03-03T13:00:00.123456+00:00')) \
            .is_equal_to(pytz.utc.localize(datetime.datetime(2022, 3, 3, 13, 0, 0, 123456)))

    def test_valid_date_exception_if_invalid(self):
        assert_that(valid_date)\
            .raises(ValueError) \
            .when_called_with(None, '--date-after', '2022-03-x')\
            .is_equal_to('option --date-after: invalid date format: 2022-03-x')

