import os
import tempfile

import requests

from attachment_downloader.version_info import Version


def send_email_with_attachment(api_key, domain, sender, recipient, subject, text, attachment_path):
    url = f"https://api.eu.mailgun.net/v3/{domain}/messages"

    with open(attachment_path, 'rb') as attachment_file:
        response = requests.post(
            url,
            auth=("api", api_key),
            files=[("attachment", (attachment_path, attachment_file.read()))],
            data={
                "from": sender,
                "to": recipient,
                "subject": subject,
                "text": text,
            }
        )
    return response.status_code == 200

class TestSendAndDownloadAttachment:
    def test_send_and_download_attachment(self):
        mailgun_domain = os.getenv('MAILGUN_DOMAIN')
        mailgun_api_key = os.getenv('MAILGUN_API_KEY')
        recipient = os.getenv('AD_INT_TEST_RECIPIENT')
        version_info = Version.commit_hash_short()

        with tempfile.NamedTemporaryFile(mode='w+t',prefix=version_info,suffix='.txt') as temp_attachment:
            temp_attachment.write(f"This is an example attachment from attachment-downloader {version_info}")
            temp_attachment.flush()

            send_email_with_attachment(mailgun_api_key,
                                       mailgun_domain,
                                       f'attachment-downloader@{mailgun_domain}',
                                       recipient,
                                       f"Integration Test - {version_info}",
                                       'This email is part of an automated integration test.',
                                       temp_attachment.name)
