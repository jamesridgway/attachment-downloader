import base64
import datetime
import email
import pathlib

import pytest
from assertpy import assert_that
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs7, pkcs12
from cryptography.x509.oid import NameOID
from imbox.parser import parse_email

from attachment_downloader.smime import SmimeDecryptor, SmimeError, is_encrypted, unwrap_message

FIXTURES = pathlib.Path(__file__).parent.parent / 'fixtures' / 'smime'

INNER_MESSAGE = (b'Content-Type: multipart/mixed; boundary="b"\r\n\r\n'
                 b'--b\r\nContent-Type: text/plain\r\n\r\nhello\r\n'
                 b'--b\r\nContent-Type: application/pdf; name="invoice.pdf"\r\n'
                 b'Content-Disposition: attachment; filename="invoice.pdf"\r\n'
                 b'Content-Transfer-Encoding: base64\r\n\r\nSGVsbG8gUERG\r\n'
                 b'--b--\r\n')

OUTER_HEADERS = (b'From: sender@example.com\r\n'
                 b'To: recipient@example.com\r\n'
                 b'Subject: Invoice 123\r\n'
                 b'Date: Thu, 03 Mar 2022 13:00:00 +0000\r\n'
                 b'Message-ID: <123@example.com>\r\n')


def generate_credentials(common_name='recipient@example.com'):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = x509.CertificateBuilder() \
        .subject_name(name) \
        .issuer_name(name) \
        .public_key(key.public_key()) \
        .serial_number(x509.random_serial_number()) \
        .not_valid_before(now) \
        .not_valid_after(now + datetime.timedelta(days=1)) \
        .sign(key, hashes.SHA256())
    return key, cert


def encrypt(data, cert):
    return pkcs7.PKCS7EnvelopeBuilder() \
        .set_data(data) \
        .add_recipient(cert) \
        .encrypt(serialization.Encoding.SMIME, [])


def opaque_signed_entity(der_data):
    return (b'Content-Type: application/pkcs7-mime; smime-type=signed-data; name="smime.p7m"\r\n'
            b'Content-Transfer-Encoding: base64\r\n\r\n' + base64.encodebytes(der_data))


def sign(data, key, cert, options=()):
    return opaque_signed_entity(pkcs7.PKCS7SignatureBuilder()
                                .set_data(data)
                                .add_signer(cert, key, hashes.SHA256())
                                .sign(serialization.Encoding.DER, list(options)))


def encrypted_message(cert):
    return parse_email(OUTER_HEADERS + encrypt(INNER_MESSAGE, cert))


@pytest.fixture(name='credentials')
def credentials_fixture():
    return generate_credentials()


class TestSmime:
    def test_is_encrypted(self, credentials):
        _, cert = credentials
        assert_that(is_encrypted(email.message_from_string(encrypted_message(cert).raw_email))).is_true()
        assert_that(is_encrypted(email.message_from_bytes(OUTER_HEADERS + INNER_MESSAGE))).is_false()

    def test_is_encrypted_ignores_signed_data(self, credentials):
        key, cert = credentials
        assert_that(is_encrypted(email.message_from_bytes(sign(INNER_MESSAGE, key, cert)))).is_false()

    def test_is_encrypted_invalid_structure(self):
        message = email.message_from_bytes(
            b'Content-Type: application/pkcs7-mime; smime-type=enveloped-data\r\n'
            b'Content-Transfer-Encoding: base64\r\n\r\nbm90IGFzbjE=\r\n')
        assert_that(is_encrypted).raises(SmimeError).when_called_with(message)

    def test_decrypt_message(self, credentials):
        key, cert = credentials
        message = encrypted_message(cert)
        assert_that(message.attachments).extracting('filename').does_not_contain('invoice.pdf')

        decrypted = unwrap_message(message, SmimeDecryptor(cert, key))

        assert_that(decrypted.subject).is_equal_to('Invoice 123')
        assert_that(decrypted.message_id).is_equal_to('<123@example.com>')
        assert_that(decrypted.date).is_equal_to('Thu, 03 Mar 2022 13:00:00 +0000')
        assert_that(decrypted.sent_from).is_equal_to([{'name': '', 'email': 'sender@example.com'}])
        assert_that(decrypted.attachments).extracting('filename').is_equal_to(['invoice.pdf'])
        assert_that(decrypted.attachments[0]['content'].read()).is_equal_to(b'Hello PDF')

    def test_decrypt_message_unencrypted_is_unchanged(self, credentials):
        key, cert = credentials
        message = parse_email(OUTER_HEADERS + INNER_MESSAGE)
        assert_that(unwrap_message(message, SmimeDecryptor(cert, key))).is_same_as(message)

    def test_decrypt_message_wrong_key(self, credentials):
        _, cert = credentials
        other_key, other_cert = generate_credentials('someone-else@example.com')
        assert_that(unwrap_message) \
            .raises(SmimeError) \
            .when_called_with(encrypted_message(cert), SmimeDecryptor(other_cert, other_key))

    def test_unwrap_message_encrypted_without_decryptor_is_unchanged(self, credentials):
        _, cert = credentials
        message = encrypted_message(cert)
        assert_that(unwrap_message(message)).is_same_as(message)

    def test_unwrap_message_opaque_signed(self, credentials):
        key, cert = credentials
        message = parse_email(OUTER_HEADERS + sign(INNER_MESSAGE, key, cert))
        assert_that(message.attachments).extracting('filename').does_not_contain('invoice.pdf')

        unwrapped = unwrap_message(message)

        assert_that(unwrapped.subject).is_equal_to('Invoice 123')
        assert_that(unwrapped.attachments).extracting('filename').is_equal_to(['invoice.pdf'])
        assert_that(unwrapped.attachments[0]['content'].read()).is_equal_to(b'Hello PDF')

    def test_unwrap_message_opaque_signed_then_encrypted(self, credentials):
        key, cert = credentials
        message = parse_email(OUTER_HEADERS + encrypt(sign(INNER_MESSAGE, key, cert), cert))

        unwrapped = unwrap_message(message, SmimeDecryptor(cert, key))

        assert_that(unwrapped.subject).is_equal_to('Invoice 123')
        assert_that(unwrapped.attachments).extracting('filename').is_equal_to(['invoice.pdf'])

    def test_unwrap_message_opaque_signed_ber(self):
        # Generated by `openssl smime -sign -nodetach -stream`, which uses BER indefinite lengths
        message = parse_email((FIXTURES / 'opaque-signed-ber.eml').read_bytes())

        unwrapped = unwrap_message(message)

        assert_that(unwrapped.subject).is_equal_to('Streamed invoice')
        assert_that(unwrapped.attachments).extracting('filename').is_equal_to(['inv.pdf'])
        assert_that(unwrapped.attachments[0]['content'].read()).is_equal_to(b'Hello PDF')

    def test_unwrap_message_detached_signature(self, credentials):
        key, cert = credentials
        message = parse_email(OUTER_HEADERS + sign(INNER_MESSAGE, key, cert, [pkcs7.PKCS7Options.DetachedSignature]))
        assert_that(unwrap_message) \
            .raises(SmimeError) \
            .when_called_with(message) \
            .is_equal_to('S/MIME signed-data does not contain any content')

    def test_unwrap_message_nested_too_deep(self, credentials):
        key, cert = credentials
        data = INNER_MESSAGE
        for _ in range(6):
            data = sign(data, key, cert)
        assert_that(unwrap_message).raises(SmimeError).when_called_with(parse_email(OUTER_HEADERS + data))

    def test_load_pem(self, credentials, tmp_path):
        key, cert = credentials
        key_path = tmp_path / 'key.pem'
        cert_path = tmp_path / 'cert.pem'
        key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                               serialization.BestAvailableEncryption(b'secret')))
        cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))

        decryptor = SmimeDecryptor.load(str(key_path), str(cert_path), 'secret')

        assert_that(decryptor.certificate).is_equal_to(cert)
        assert_that(unwrap_message(encrypted_message(cert), decryptor).attachments).is_length(1)

    def test_load_pem_requires_cert(self, credentials, tmp_path):
        key, _ = credentials
        key_path = tmp_path / 'key.pem'
        key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                               serialization.NoEncryption()))
        assert_that(SmimeDecryptor.load) \
            .raises(SmimeError) \
            .when_called_with(str(key_path)) \
            .is_equal_to('--smime-cert is required when --smime-key is a PEM private key')

    def test_load_pkcs12(self, credentials, tmp_path):
        key, cert = credentials
        p12_path = tmp_path / 'credentials.p12'
        p12_path.write_bytes(pkcs12.serialize_key_and_certificates(
            b'test', key, cert, None, serialization.BestAvailableEncryption(b'secret')))

        decryptor = SmimeDecryptor.load(str(p12_path), password='secret')

        assert_that(decryptor.certificate).is_equal_to(cert)
        assert_that(unwrap_message(encrypted_message(cert), decryptor).attachments).is_length(1)

    def test_load_pkcs12_wrong_password(self, credentials, tmp_path):
        key, cert = credentials
        p12_path = tmp_path / 'credentials.p12'
        p12_path.write_bytes(pkcs12.serialize_key_and_certificates(
            b'test', key, cert, None, serialization.BestAvailableEncryption(b'secret')))
        assert_that(SmimeDecryptor.load).raises(SmimeError).when_called_with(str(p12_path), None, 'wrong')

    def test_load_missing_file(self):
        assert_that(SmimeDecryptor.load).raises(SmimeError).when_called_with('/does/not/exist.pem')
