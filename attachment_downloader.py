import imaplib
import logging
from getpass import getpass
from optparse import OptionParser

import sys

import os

from mail_message import MailMessage


class AttachmentDownloader:
    def __init__(self, host):
        self.mail = imaplib.IMAP4_SSL(host)

    def login(self, username, password):
        self.mail.login(username, password)

    def list_messages(self, imap_folder):

        select_status, _ = self.mail.select(imap_folder)

        if select_status != 'OK':
            print("Folder not found")
            return

        search_status, search_data = self.mail.search(None, "ALL")
        if search_status != 'OK':
            print("No messages found!")
            return

        messages = []
        for num in search_data[0].split():
            fetch_status, data = self.mail.fetch(num, '(RFC822)')
            if fetch_status != 'OK':
                print("ERROR getting message", num)
                return
            messages.append(MailMessage(data[0][1]))

        self.mail.close()
        return messages

    def logout(self):
        self.mail.logout()


if __name__ == '__main__':

    std_out_stream_handler = logging.StreamHandler(sys.stdout)
    std_out_stream_handler.setLevel(logging.DEBUG)
    std_out_stream_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(std_out_stream_handler)

    parser = OptionParser()
    parser.add_option("--host", dest="host", help="IMAP Host")
    parser.add_option("--username", dest="username", help="IMAP Username")
    parser.add_option("--password", dest="password", help="IMAP Password")
    parser.add_option("--imap-folder", dest="imap_folder", help="IMAP Folder to extract attachments from")
    parser.add_option("--output", dest="download_folder", help="Output directory for attachment download")

    (options, args) = parser.parse_args()

    if not options.host:
        parser.error('--host parameter required')
    if not options.username:
        parser.error('--username parameter required')
    if not options.imap_folder:
        parser.error('--folder parameter required')
    if not options.download_folder:
        parser.error('--output parameter required')

    password = options.password if options.password else getpass('IMAP Password: ')

    downloader = AttachmentDownloader(options.host)

    logging.info("Logging in to: '%s' as '%s'", options.host, options.username)
    downloader.login(options.username, password)

    logging.info("Listing messages folder folder: %s", options.imap_folder)
    messages = downloader.list_messages(options.imap_folder)

    for message in messages:
        for attachment_name in message.list_attachments():
            download_filename = os.path.join(options.download_folder, attachment_name)
            logging.info("Downloading attachment '%s' for message '%s': %s", attachment_name, message.subject, download_filename)
            fp = open(download_filename, 'wb')
            fp.write(message.get_attachment_payload(attachment_name))
            fp.close()
    logging.info('Finished processing messages')

    logging.info('Logging out of: %s', options.host)
    downloader.logout()

    logging.info("Done")

