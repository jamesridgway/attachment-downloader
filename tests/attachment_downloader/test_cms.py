import email
import pathlib

import pytest
from assertpy import assert_that
from imbox.parser import parse_email

from attachment_downloader.cms import CmsError, decrypt
from attachment_downloader.smime import SmimeDecryptor, SmimeError, is_encrypted, unwrap_message

FIXTURES = pathlib.Path(__file__).parent.parent / 'fixtures' / 'smime'

RSA_FIXTURES = ['aes256-cbc-ber', 'aes128-gcm', 'aes256-gcm', 'rsa-oaep-sha1', 'rsa-oaep-sha256',
                'rsa-key-identifier']
EC_FIXTURES = ['ec-sha1kdf', 'ec-sha256kdf-gcm']


def load_decryptor(key_type):
    return SmimeDecryptor.load(str(FIXTURES / f'{key_type}-key.pem'), str(FIXTURES / f'{key_type}-cert.pem'))


def fixture_payload(name):
    return email.message_from_bytes((FIXTURES / f'{name}.eml').read_bytes()).get_payload(decode=True)


class TestCms:
    @pytest.mark.parametrize('name,key_type', [(name, 'rsa') for name in RSA_FIXTURES] +
                             [(name, 'ec') for name in EC_FIXTURES])
    def test_unwrap_message(self, name, key_type):
        message = parse_email((FIXTURES / f'{name}.eml').read_bytes())
        assert_that(is_encrypted(email.message_from_string(message.raw_email))).is_true()

        unwrapped = unwrap_message(message, load_decryptor(key_type))

        assert_that(unwrapped.subject).is_equal_to(name)
        assert_that(unwrapped.sent_from).is_equal_to([{'name': '', 'email': 'sender@example.com'}])
        assert_that(unwrapped.attachments).extracting('filename').is_equal_to(['invoice.pdf'])
        assert_that(unwrapped.attachments[0]['content'].read()).is_equal_to(b'Hello PDF')

    def test_decrypt_tampered_gcm(self):
        # The MAC is the final element of the authenticated enveloped-data structure
        payload = bytearray(fixture_payload('aes256-gcm'))
        payload[-1] ^= 0x01
        decryptor = load_decryptor('rsa')
        assert_that(decrypt) \
            .raises(CmsError) \
            .when_called_with(bytes(payload), decryptor.certificate, decryptor.private_key) \
            .is_equal_to('Unable to decrypt content, the message may have been tampered with')

    def test_decrypt_wrong_recipient(self):
        decryptor = load_decryptor('ec')
        assert_that(decrypt) \
            .raises(CmsError) \
            .when_called_with(fixture_payload('aes256-gcm'), decryptor.certificate, decryptor.private_key) \
            .is_equal_to('Message is not encrypted for the provided certificate')

    def test_decrypt_wrong_key_type(self):
        rsa_decryptor = load_decryptor('rsa')
        ec_decryptor = load_decryptor('ec')
        assert_that(decrypt) \
            .raises(CmsError) \
            .when_called_with(fixture_payload('ec-sha1kdf'), ec_decryptor.certificate, rsa_decryptor.private_key) \
            .is_equal_to('An EC private key is required to decrypt this message')

    def test_decrypt_invalid_structure(self):
        decryptor = load_decryptor('rsa')
        assert_that(decrypt) \
            .raises(CmsError) \
            .when_called_with(b'\x30\x03\x02\x01\x00', decryptor.certificate, decryptor.private_key)

    def test_unwrap_message_wraps_errors(self):
        message = parse_email((FIXTURES / 'aes256-gcm.eml').read_bytes())
        assert_that(unwrap_message).raises(SmimeError).when_called_with(message, load_decryptor('ec'))
