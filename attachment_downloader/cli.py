"""
Command line interface.
"""
import datetime
import logging
import os
import ssl
import sys
import time
from copy import copy
from getpass import getpass
from optparse import Option, OptionParser, OptionValueError

from imbox import Imbox
from iso8601 import iso8601
from jinja2 import Template, TemplateError

from attachment_downloader.downloader import AttachmentDownloader, validate_filename_template
from attachment_downloader.logging import LEVELS, Logger
from attachment_downloader.smime import SmimeDecryptor, SmimeError
from attachment_downloader.version_info import Version

ENVIRONMENT_PREFIX = 'AD_'
TRUE_VALUES = ('1', 'true', 'yes', 'on')


def valid_date(_, opt, value):
    """
    Parse date input string into a datetime object.
    """
    try:
        parsed_value = iso8601.parse_date(value)
        if not parsed_value.tzinfo:
            parsed_value = parsed_value.replace(tzinfo=datetime.timezone.utc)
        return parsed_value
    except ValueError as ex:
        raise ValueError(f'option {opt}: invalid date format: {value}') from ex


def get_password():
    """
    Prompt for password via getpass/stdin.
    """
    if sys.stdin.isatty():
        return getpass('IMAP Password: ')
    return sys.stdin.read().strip()


class AttachmentDownloaderOption(Option):
    """
    Adds the 'date' option type.
    """
    TYPES = Option.TYPES + ('date',)
    TYPE_CHECKER = copy(Option.TYPE_CHECKER)
    TYPE_CHECKER['date'] = valid_date


def build_parser():
    """
    The command line option parser.
    """
    parser = OptionParser(option_class=AttachmentDownloaderOption)
    parser.add_option("--host", dest="host", help="IMAP Host")
    parser.add_option("--username", dest="username", help="IMAP Username")
    parser.add_option("--password", dest="password", help="IMAP Password")
    parser.add_option("--imap-folder", dest="imap_folder", help="IMAP Folder to extract attachments from")
    parser.add_option("--filename-regex", dest="filename_regex",
                      help="Regex that the attachment filename must match against")
    parser.add_option("--sent-to-regex", dest="sent_to_regex", help="Regex that the sent_to must match against")
    parser.add_option("--subject-regex", dest="subject_regex", help="Regex that the subject must match against")
    parser.add_option("--subject-regex-ignore-case", dest="subject_regex_ignore_case", action="store_true",
                      default=False, help="Provide this option to ignore regex case in subject.")
    parser.add_option("--subject-regex-match-anywhere", dest="subject_regex_match_anywhere", action="store_true",
                      default=False, help="Provide this option to search anywhere in subject")
    parser.add_option("--date-after", dest="date_after", type='date', help='Select messages after this date')
    parser.add_option("--date-before", dest="date_before", type='date', help='Select messages before this date')
    parser.add_option("--filename-template", dest="filename_template", help="Attachment filename (jinja2) template.",
                      default="{{ attachment_name }}")
    parser.add_option("--output", dest="download_folder", help="Output directory for attachment download")
    parser.add_option("--delete", dest="delete", action="store_true", help="Delete downloaded emails from Mailbox")
    parser.add_option("--delete-copy-folder", dest="delete_copy_folder",
                      help="IMAP folder to copy emails to before deleting them")
    parser.add_option("--port", dest="port", type=int,
                      help="Specify imap server port (defaults to 993 for TLS and 143 otherwise")
    parser.add_option("--unsecure", dest="unsecure", action="store_true",
                      help="disable encrypted connection (not recommended)")
    parser.add_option("--starttls", dest="starttls", action="store_true", help="enable STARTTLS (not recommended)")
    parser.add_option("--smime-key", dest="smime_key",
                      help="Private key used to decrypt S/MIME encrypted emails (PEM, or a PKCS#12 .p12/.pfx bundle)")
    parser.add_option("--smime-cert", dest="smime_cert",
                      help="Certificate (PEM) used to decrypt S/MIME encrypted emails (optional for PKCS#12 bundles)")
    parser.add_option("--smime-key-password", dest="smime_key_password",
                      help="Password for the S/MIME private key or PKCS#12 bundle")
    parser.add_option("--log-level", dest="loglevel", default="INFO",
                      help="Set the log level to DEBUG, INFO, WARNING, ERROR, or CRITICAL (default is INFO)")
    return parser


def parse_options(parser, args=None, environ=None):
    """
    Parse the command line, using AD_<OPTION> environment variables for any option that is not given.
    """
    environ = os.environ if environ is None else environ
    options, _ = parser.parse_args(args)

    for option in parser.option_list:
        if not option.dest or getattr(options, option.dest):
            continue
        value = environ.get(ENVIRONMENT_PREFIX + option.dest.upper())
        if value:
            setattr(options, option.dest, environment_value(parser, option, value))

    validate_options(parser, options)
    return options


def environment_value(parser, option, value):
    """
    Convert an environment variable to the same type as the command line option would be.
    """
    if option.action == 'store_true':
        return value.lower() in TRUE_VALUES
    try:
        return option.check_value(option.get_opt_string(), value)
    except (OptionValueError, ValueError) as ex:
        return parser.error(f'{ENVIRONMENT_PREFIX}{option.dest.upper()}: {ex}')


def validate_options(parser, options):
    """
    Check that the options are complete and consistent.
    """
    if not options.host:
        parser.error('--host parameter required')
    if not options.username:
        parser.error('--username parameter required')
    if not options.download_folder:
        parser.error('--output parameter required')
    if options.delete_copy_folder and not options.delete:
        parser.error('--delete parameter required when using --delete-copy-folder')
    if options.unsecure and options.starttls:
        parser.error('--unsecure and --starttls are exclusive')
    if options.smime_cert and not options.smime_key:
        parser.error('--smime-key parameter required when using --smime-cert')
    if options.loglevel.upper() not in LEVELS:
        parser.error(f'--log-level must be one of {", ".join(LEVELS)}')


def load_filename_template(parser, source):
    """
    Load and validate the filename template.
    """
    try:
        template = Template(source)
        validate_filename_template(template)
        return template
    except TemplateError as ex:
        return parser.error(f'--filename-template is invalid: {ex}')


def load_smime_decryptor(parser, options):
    """
    Load the S/MIME credentials, if provided.
    """
    if not options.smime_key:
        return None
    try:
        decryptor = SmimeDecryptor.load(options.smime_key, options.smime_cert, options.smime_key_password)
    except SmimeError as ex:
        return parser.error(str(ex))
    logging.info("S/MIME decryption enabled for certificate: %s", decryptor.certificate.subject.rfc4514_string())
    return decryptor


def connect(options, password):
    """
    Connect to the IMAP server.
    """
    logging.info("Logging in to: '%s' as '%s'", options.host, options.username)
    mailbox = Imbox(options.host,
                    username=options.username,
                    password=password,
                    port=options.port,
                    ssl=not options.unsecure and not options.starttls,
                    ssl_context=ssl.create_default_context(),
                    starttls=bool(options.starttls))
    logging.info("Logged in to: '%s' as '%s'", options.host, options.username)
    return mailbox


def main(args=None):
    """
    Entry point for the attachment-downloader command.
    """
    parser = build_parser()
    options = parse_options(parser, args)

    Logger.setup(options.loglevel)
    logging.info('Attachment Downloader - Version: %s %s', Version.get(), Version.get_env_info())

    filename_template = load_filename_template(parser, options.filename_template)
    smime_decryptor = load_smime_decryptor(parser, options)
    password = options.password or get_password()
    interval = os.getenv(ENVIRONMENT_PREFIX + 'INTERVAL')

    while True:
        with connect(options, password) as mailbox:
            AttachmentDownloader(mailbox, options, filename_template, smime_decryptor).run()
            logging.info('Logging out of: %s', options.host)
        if interval is None:
            break
        time.sleep(int(interval))

    logging.info("Done")
