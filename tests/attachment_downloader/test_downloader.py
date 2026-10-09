import datetime
from types import SimpleNamespace

import pytest
from assertpy import assert_that
from imbox.parser import parse_email
from jinja2 import Template

from attachment_downloader.downloader import AttachmentDownloader, folder_name


def build_message(subject='Invoice 123', date='Thu, 03 Mar 2022 13:00:00 +0000', to='recipient@example.com',
                  attachments=('invoice.pdf',)):
    parts = ''.join(f'--b\r\nContent-Type: application/pdf\r\nContent-Disposition: attachment; filename="{name}"\r\n'
                    f'Content-Transfer-Encoding: base64\r\n\r\nSGVsbG8gUERG\r\n' for name in attachments)
    return parse_email(f'From: sender@example.com\r\nTo: {to}\r\nSubject: {subject}\r\nDate: {date}\r\n'
                       f'Message-ID: <123@example.com>\r\nContent-Type: multipart/mixed; boundary="b"\r\n\r\n'
                       f'{parts}--b--\r\n'.encode())


class FakeMailbox:
    def __init__(self, messages, folders=()):
        self.message_list = messages
        self.folder_list = folders
        self.copied = []
        self.deleted = []

    def messages(self, **_):
        return self.message_list

    def folders(self):
        return 'OK', list(self.folder_list)

    def copy(self, uid, folder):
        self.copied.append((uid, folder))

    def delete(self, uid):
        self.deleted.append(uid)


def build_options(download_folder, **overrides):
    options = dict(imap_folder='INBOX', date_after=None, date_before=None, subject_regex=None,
                   subject_regex_ignore_case=False, subject_regex_match_anywhere=False, sent_to_regex=None,
                   filename_regex=None, download_folder=str(download_folder), delete=False, delete_copy_folder=None)
    options.update(overrides)
    return SimpleNamespace(**options)


def run(tmp_path, messages, template='{{ attachment_name }}', **options):
    mailbox = FakeMailbox(messages)
    AttachmentDownloader(mailbox, build_options(tmp_path, **options), Template(template)).run()
    return mailbox


def downloaded(tmp_path):
    return sorted(str(path.relative_to(tmp_path)) for path in tmp_path.rglob('*') if path.is_file())


class TestAttachmentDownloader:
    def test_downloads_attachments(self, tmp_path):
        run(tmp_path, [('1', build_message(attachments=('a.pdf', 'b.pdf')))])
        assert_that(downloaded(tmp_path)).is_equal_to(['a.pdf', 'b.pdf'])
        assert_that((tmp_path / 'a.pdf').read_bytes()).is_equal_to(b'Hello PDF')

    def test_filename_template(self, tmp_path):
        run(tmp_path, [('1', build_message())],
            template="{{ date.strftime('%Y-%m-%d') }}/{{ from_email }}/{{ attachment_idx }}-{{ attachment_name }}")
        assert_that(downloaded(tmp_path)).is_equal_to(['2022-03-03/sender@example.com/0-invoice.pdf'])

    @pytest.mark.parametrize('options,expected', [
        ({'subject_regex': 'Invoice'}, ['match.pdf']),
        ({'subject_regex': 'invoice'}, []),
        ({'subject_regex': 'invoice', 'subject_regex_ignore_case': True}, ['match.pdf']),
        ({'subject_regex': '123'}, []),
        ({'subject_regex': '123', 'subject_regex_match_anywhere': True}, ['match.pdf']),
        ({'sent_to_regex': '@example.com'}, ['match.pdf']),
        ({'sent_to_regex': '@example.org'}, []),
        ({'filename_regex': r'\.pdf$'}, ['match.pdf']),
        ({'filename_regex': r'\.docx$'}, []),
    ])
    def test_filters(self, tmp_path, options, expected):
        run(tmp_path, [('1', build_message(attachments=('match.pdf',)))], **options)
        assert_that(downloaded(tmp_path)).is_equal_to(expected)

    def test_date_filters(self, tmp_path):
        messages = [('1', build_message(date='Wed, 02 Mar 2022 13:00:00 +0000', attachments=('before.pdf',))),
                    ('2', build_message(date='Thu, 03 Mar 2022 13:00:00 +0000', attachments=('during.pdf',))),
                    ('3', build_message(date='Fri, 04 Mar 2022 13:00:00 +0000', attachments=('after.pdf',)))]
        run(tmp_path, messages, date_after=datetime.datetime(2022, 3, 3, tzinfo=datetime.timezone.utc),
            date_before=datetime.datetime(2022, 3, 4, tzinfo=datetime.timezone.utc))
        assert_that(downloaded(tmp_path)).is_equal_to(['during.pdf'])

    def test_date_without_timezone_is_treated_as_utc(self, tmp_path):
        messages = [('1', build_message(date='Thu, 03 Mar 2022 13:00:00', attachments=('first.pdf',))),
                    ('2', build_message(attachments=('second.pdf',)))]
        run(tmp_path, messages, date_after=datetime.datetime(2022, 3, 1, tzinfo=datetime.timezone.utc))
        assert_that(downloaded(tmp_path)).is_equal_to(['first.pdf', 'second.pdf'])

    def test_unparseable_date_skips_only_that_message(self, tmp_path):
        messages = [('1', build_message(date='not a date', attachments=('first.pdf',))),
                    ('2', build_message(attachments=('second.pdf',)))]
        run(tmp_path, messages)
        assert_that(downloaded(tmp_path)).is_equal_to(['second.pdf'])

    def test_delete_copies_and_deletes_once_per_message(self, tmp_path):
        mailbox = run(tmp_path, [('1', build_message(attachments=('a.pdf', 'b.pdf')))], delete=True,
                      delete_copy_folder='Archive')
        assert_that(mailbox.copied).is_equal_to([('1', '"Archive"')])
        assert_that(mailbox.deleted).is_equal_to(['1'])

    def test_delete_with_bytes_uid(self, tmp_path):
        mailbox = run(tmp_path, [(b'7', build_message())], delete=True)
        assert_that(mailbox.deleted).is_equal_to(['7'])

    def test_delete_skips_messages_without_downloads(self, tmp_path):
        mailbox = run(tmp_path, [('1', build_message())], delete=True, filename_regex=r'\.docx$')
        assert_that(mailbox.deleted).is_empty()

    def test_delete_skips_messages_with_a_failed_download(self, tmp_path):
        (tmp_path / 'b.pdf').mkdir()
        mailbox = run(tmp_path, [('1', build_message(attachments=('a.pdf', 'b.pdf')))], delete=True)
        assert_that(downloaded(tmp_path)).is_equal_to(['a.pdf'])
        assert_that(mailbox.deleted).is_empty()

    def test_all_folders(self, tmp_path):
        mailbox = FakeMailbox([], folders=[b'(\\HasNoChildren) "/" "INBOX"', b'(\\Noselect) "/" "[Gmail]"',
                                           b'(\\HasNoChildren) "/" "[Gmail]/Sent Mail"'])
        folders = AttachmentDownloader(mailbox, build_options(tmp_path, imap_folder=None), Template('')).folders()
        assert_that(folders).is_equal_to(['"INBOX"', '"[Gmail]/Sent Mail"'])


class TestFolderName:
    @pytest.mark.parametrize('list_response,expected', [
        (b'(\\HasNoChildren) "/" "INBOX"', '"INBOX"'),
        (b'(\\HasNoChildren) "." "INBOX.Sent"', '"INBOX.Sent"'),
        (b'(\\HasNoChildren) "/" INBOX', 'INBOX'),
        (b'() NIL "Shared"', '"Shared"'),
    ])
    def test_folder_name(self, list_response, expected):
        assert_that(folder_name(list_response)).is_equal_to(expected)

    def test_folder_name_invalid(self):
        assert_that(folder_name).raises(ValueError).when_called_with(b'nonsense')
