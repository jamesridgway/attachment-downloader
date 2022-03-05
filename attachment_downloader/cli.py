import datetime
import sys
from getpass import getpass
from optparse import OptionValueError


def valid_date(option, opt, value):
    try:
        parsed_value = datetime.datetime.fromisoformat(value)
        if not parsed_value.tzinfo:
            parsed_value = parsed_value.replace(tzinfo=datetime.timezone.utc)
        return parsed_value
    except ValueError:
        raise OptionValueError('option %s: invalid date format: %r' % (opt, value))


def get_password():
    if sys.stdin.isatty():
        return getpass('IMAP Password: ')
    else:
        return sys.stdin.read().strip()
