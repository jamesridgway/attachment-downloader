import datetime

import pytz as pytz
from assertpy import assert_that

import pytest

from attachment_downloader.cli import build_parser, parse_options, valid_date

REQUIRED_ARGS = ['--host', 'imap.example.com', '--username', 'user', '--output', 'downloads']


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


    def test_parse_options(self):
        options = parse_options(build_parser(), REQUIRED_ARGS + ['--port', '1993', '--delete'], environ={})
        assert_that(options.host).is_equal_to('imap.example.com')
        assert_that(options.port).is_equal_to(1993)
        assert_that(options.delete).is_true()

    def test_parse_options_from_environment(self):
        options = parse_options(build_parser(), [], environ={
            'AD_HOST': 'imap.example.com', 'AD_USERNAME': 'user', 'AD_DOWNLOAD_FOLDER': 'downloads',
            'AD_PORT': '1993', 'AD_DATE_AFTER': '2022-03-03T13:00:00', 'AD_DELETE': 'true'})
        assert_that(options.host).is_equal_to('imap.example.com')
        assert_that(options.port).is_equal_to(1993)
        assert_that(options.date_after).is_equal_to(pytz.utc.localize(datetime.datetime(2022, 3, 3, 13, 0, 0)))
        assert_that(options.delete).is_true()

    @pytest.mark.parametrize('value', ['false', '0', 'no'])
    def test_parse_options_false_environment_flag(self, value):
        options = parse_options(build_parser(), REQUIRED_ARGS, environ={'AD_DELETE': value})
        assert_that(options.delete).is_false()

    def test_parse_options_from_environment_overrides_defaults(self):
        options = parse_options(build_parser(), REQUIRED_ARGS, environ={
            'AD_FILENAME_TEMPLATE': '{{ subject }}/{{ attachment_name }}', 'AD_LOGLEVEL': 'DEBUG'})
        assert_that(options.filename_template).is_equal_to('{{ subject }}/{{ attachment_name }}')
        assert_that(options.loglevel).is_equal_to('DEBUG')

    def test_parse_options_command_line_flag_overrides_environment(self):
        options = parse_options(build_parser(), REQUIRED_ARGS + ['--filename-template', '{{ date }}'],
                                environ={'AD_FILENAME_TEMPLATE': '{{ subject }}'})
        assert_that(options.filename_template).is_equal_to('{{ date }}')

    def test_parse_options_command_line_takes_precedence(self):
        options = parse_options(build_parser(), REQUIRED_ARGS, environ={'AD_HOST': 'other.example.com'})
        assert_that(options.host).is_equal_to('imap.example.com')

    @pytest.mark.parametrize('args,environ', [
        (['--host', 'imap.example.com', '--username', 'user'], {}),
        (REQUIRED_ARGS + ['--delete-copy-folder', 'Archive'], {}),
        (REQUIRED_ARGS + ['--unsecure', '--starttls'], {}),
        (REQUIRED_ARGS + ['--smime-cert', 'cert.pem'], {}),
        (REQUIRED_ARGS, {'AD_PORT': 'not a number'}),
        (REQUIRED_ARGS + ['--log-level', 'LOUD'], {}),
    ])
    def test_parse_options_invalid(self, args, environ):
        with pytest.raises(SystemExit):
            parse_options(build_parser(), args, environ=environ)
