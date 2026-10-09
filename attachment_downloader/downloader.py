"""
Downloads the attachments of the messages in an IMAP mailbox.
"""
import datetime
import logging
import os
import re
from dataclasses import dataclass

import dateutil.parser
from jinja2 import TemplateError

from attachment_downloader.encoding import QuoPriEncoding
from attachment_downloader.smime import SmimeError, unwrap_message

LIST_RESPONSE = re.compile(r'\((?P<flags>[^)]*)\) (?P<delimiter>"[^"]*"|NIL) (?P<name>.+)')
EXCLUDED_FOLDERS = ('"[Gmail]"',)


@dataclass
class MessageSummary:
    """
    The details of a message that are used to filter it and to name its attachments.
    """
    uid: str
    message_id: str
    subject: str
    date: datetime.datetime
    sent_to: list
    sent_from: str

    @property
    def sent_to_display(self):
        """
        The first recipient, for logging.
        """
        return self.sent_to[0] if self.sent_to else '(no recipient)'


def summarise(uid, message):
    """
    Summarise an imbox message. Raises ValueError if the message date is missing or cannot be parsed.
    """
    date = dateutil.parser.parse(message.date)
    if date.tzinfo is None:
        date = date.replace(tzinfo=datetime.timezone.utc)
    sent_from = getattr(message, 'sent_from', None) or []
    return MessageSummary(
        uid=uid,
        message_id=getattr(message, 'message_id', ''),
        subject=QuoPriEncoding.decode(message.subject) if hasattr(message, 'subject') else '',
        date=date,
        sent_to=[recipient['email'] for recipient in getattr(message, 'sent_to', None) or []],
        sent_from=sent_from[0]['email'] if sent_from else '(unknown)',
    )


def folder_name(list_response):
    """
    The folder name from an IMAP LIST response line, as returned by imbox.
    """
    match = LIST_RESPONSE.match(list_response.decode())
    if not match:
        raise ValueError(f'Unable to parse IMAP LIST response: {list_response!r}')
    return match.group('name')


def render_filename(template, attachment_name, attachment_idx, summary, folder):
    """
    Render the attachment filename template.
    """
    return template.render(attachment_name=attachment_name,
                           attachment_idx=attachment_idx,
                           subject=summary.subject,
                           message_id=summary.message_id,
                           date=summary.date,
                           folder=folder,
                           from_email=summary.sent_from)


def validate_filename_template(template):
    """
    Render the template with sample values, so that mistakes are reported before connecting to the mailbox.
    """
    sample = MessageSummary(uid='1', message_id='<sample@example.com>', subject='Subject',
                            date=datetime.datetime.now(datetime.timezone.utc), sent_to=['recipient@example.com'],
                            sent_from='sender@example.com')
    render_filename(template, 'attachment.pdf', 0, sample, 'INBOX')


class AttachmentDownloader:
    """
    Downloads the attachments of the messages in a mailbox that match the given options.
    """

    def __init__(self, mailbox, options, filename_template, smime_decryptor=None):
        self.mailbox = mailbox
        self.options = options
        self.filename_template = filename_template
        self.smime_decryptor = smime_decryptor

    def run(self):
        """
        Process every message in the selected folders.
        """
        folders = self.folders()
        logging.info("Folders: %s", folders)
        for folder in folders:
            try:
                for uid, message in self.mailbox.messages(**self.search_criteria(folder)):
                    self.process_message(uid, message, folder)
            except Exception as ex:  # pylint: disable=broad-exception-caught
                logging.error("Failed to process messages for folder '%s'", folder)
                logging.exception(ex)
        logging.info('Finished processing messages')

    def folders(self):
        """
        The folders to process: the folder given in the options, otherwise every folder in the mailbox.
        """
        if self.options.imap_folder:
            return [self.options.imap_folder]
        _, list_responses = self.mailbox.folders()
        return [name for name in map(folder_name, list_responses) if name not in EXCLUDED_FOLDERS]

    def search_criteria(self, folder):
        """
        The imbox search criteria for a folder. Dates are only filtered by day on the server, so the precise times are
        checked again for each message.
        """
        criteria = {'folder': folder}
        date_after, date_before = self.options.date_after, self.options.date_before
        if date_after and date_before and date_after.date() == date_before.date():
            criteria['date__on'] = date_after.date()
        else:
            if date_after:
                criteria['date__gt'] = date_after.date()
            if date_before:
                criteria['date__lt'] = date_before.date()
        logging.info("Listing messages matching the following criteria: %s",
                     ", ".join(f'{key}={value}' for key, value in criteria.items()))
        return criteria

    def process_message(self, uid, message, folder):
        """
        Download the attachments of a message if it matches the options, then delete it if requested.
        """
        uid = uid.decode() if isinstance(uid, bytes) else uid
        subject = getattr(message, 'subject', '')
        try:
            message = unwrap_message(message, self.smime_decryptor)
        except SmimeError as ex:
            logging.error("Skipping message '%s' subject '%s' because its S/MIME content could not be read: %s",
                          uid, subject, ex)
            return

        try:
            summary = summarise(uid, message)
        except (AttributeError, TypeError, ValueError, OverflowError):
            logging.error("Skipping message '%s' subject '%s' because its date can not be parsed: '%s'",
                          uid, subject, getattr(message, 'date', None))
            return

        skip_reason = self.skip_reason(summary)
        if skip_reason:
            logging.warning("Skipping message '%s' subject '%s' send to '%s' because %s",
                            uid, summary.subject, summary.sent_to_display, skip_reason)
            return

        logging.info("Processing message '%s' subject '%s' send to '%s'", uid, summary.subject,
                     summary.sent_to_display)
        if self.download_attachments(message, summary, folder) and self.options.delete:
            self.delete(uid)

    def skip_reason(self, summary):
        """
        Why a message does not match the options, or None if it matches.
        """
        options = self.options
        if options.sent_to_regex and not summary.sent_to:
            return 'sent_to is empty and --sent-to-regex is set'
        if options.date_after and summary.date < options.date_after:
            return f'it is before {options.date_after}'
        if options.date_before and summary.date >= options.date_before:
            return f'it is after {options.date_before}'
        if options.subject_regex and not self.subject_matches(summary.subject):
            case = 'case-insensitive' if options.subject_regex_ignore_case else 'case-sensitive'
            position = 'found in' if options.subject_regex_match_anywhere else 'at the start of'
            return f"'{options.subject_regex}' was not {position} the subject ({case})"
        if options.sent_to_regex and not any(re.search(options.sent_to_regex, email) for email in summary.sent_to):
            return f"'{options.sent_to_regex}' was not found in any sent_to email"
        return None

    def subject_matches(self, subject):
        """
        Whether the subject matches the subject regex options.
        """
        flags = re.IGNORECASE if self.options.subject_regex_ignore_case else 0
        search = re.search if self.options.subject_regex_match_anywhere else re.match
        return search(self.options.subject_regex, subject, flags=flags) is not None

    def download_attachments(self, message, summary, folder):
        """
        Save the attachments of a message that match the filename regex. Returns whether at least one attachment was
        saved and none failed.
        """
        downloaded = False
        failed = False
        for idx, attachment in enumerate(message.attachments):
            try:
                attachment_name = QuoPriEncoding.decode(attachment.get('filename'))
                if self.options.filename_regex and not re.search(self.options.filename_regex, attachment_name):
                    logging.warning("Skipping attachment '%s' because '%s' was not found in filename",
                                    attachment_name, self.options.filename_regex)
                    continue
                filename = render_filename(self.filename_template, attachment_name, idx, summary, folder)
                self.save(attachment, attachment_name, os.path.join(self.options.download_folder, filename))
                downloaded = True
            except (OSError, TemplateError, TypeError, ValueError) as ex:
                logging.exception(ex)
                logging.error('Error saving file. Continuing...')
                failed = True
        return downloaded and not failed

    @staticmethod
    def save(attachment, attachment_name, path):
        """
        Write an attachment to disk, creating its folder if required.
        """
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        logging.info("Downloading attachment '%s' to path %s", attachment_name, path)
        if os.path.isfile(path):
            logging.warning("Overwriting file: '%s'", path)
        with open(path, 'wb') as file:
            file.write(attachment.get('content').read())

    def delete(self, uid):
        """
        Delete a message, copying it to the delete copy folder first if one is set.
        """
        if self.options.delete_copy_folder:
            self.mailbox.copy(uid, f'"{self.options.delete_copy_folder}"')
        self.mailbox.delete(uid)
