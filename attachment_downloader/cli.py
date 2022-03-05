import datetime
import sys
from getpass import getpass


def valid_date(_, opt, value):
    try:
        parsed_value = datetime.datetime.fromisoformat(value)
        if not parsed_value.tzinfo:
            parsed_value = parsed_value.replace(tzinfo=datetime.timezone.utc)
        return parsed_value
    except ValueError as ex:
        raise ValueError(f'option {opt}: invalid date format: {value}') from ex


def get_password():
    if sys.stdin.isatty():
        return getpass('IMAP Password: ')
    return sys.stdin.read().strip()
