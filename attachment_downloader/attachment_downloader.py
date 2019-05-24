import datetime
import email
import imaplib

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

        data_list = search_data[0].split()        

        count = len(data_list)

        for (idx, num) in enumerate(data_list):
            print("Downloading %i of %i ..." % (idx + 1, count))
            try:
                fetch_status, data = self.mail.fetch(num, '(RFC822)')
                if fetch_status != 'OK':
                    print("ERROR getting message", num)
                    print("Continuing retrieval...")
                else:
                    messages.append(MailMessage(data[0][1]))
            except:
                print("Unexpected retrieval ERROR", num)
                print("Continuing retrieval...")

        self.mail.close()
        return messages

    def logout(self):
        self.mail.logout()

class MailMessage:
    def __init__(self, data):
        self.msg = email.message_from_string(self.decode(data))
        self.subject = self.msg['Subject']
        self.message_id = self.msg['message-id']
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

    def decode(self, data):
        encodings=('utf8', 'cp1252')
        for encoding in encodings:
            try:
                return data.decode(encoding)
            except:
                pass

    @staticmethod
    def delete(self, conn, msg_id):
        conn.delete_messages(msg_id)
        conn.expunge(msg_id)
