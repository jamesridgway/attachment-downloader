import datetime
import email
import email.header


class MailMessage:
    def __init__(self, data):
        self.msg = email.message_from_string(data.decode('utf-8'))
        self.subject = self.msg['Subject']
        self.raw_date = self.msg['Date']
        date_tuple = email.utils.parsedate_tz(self.raw_date)
        if date_tuple:
            self.local_date = datetime.datetime.fromtimestamp(email.utils.mktime_tz(date_tuple))

    def list_attachments(self):
        attachment_filenames = []
        for part in self.msg.walk():
            if part.get_content_maintype() == 'multipart':
                continue
            if part.get('Content-Disposition') is None:
                continue
            file_name = part.get_filename()
            attachment_filenames.append(file_name)
        return attachment_filenames

    def get_attachment_payload(self, attachment_filename):
        for part in self.msg.walk():
            if part.get_content_maintype() == 'multipart':
                continue
            if part.get('Content-Disposition') is None:
                continue
            file_name = part.get_filename()
            if file_name == attachment_filename:
                return part.get_payload(decode=True)