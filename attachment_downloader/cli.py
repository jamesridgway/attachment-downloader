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
        raise OptionValueError(f'option {opt}: invalid date format: {value}')


def get_password():
    if sys.stdin.isatty():
        return getpass('IMAP Password: ')
    return sys.stdin.read().strip()
