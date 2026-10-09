"""
S/MIME decryption support.
"""
import email
from email.policy import compat32

from cryptography import x509
from cryptography.hazmat.primitives.serialization import load_pem_private_key, pkcs7, pkcs12
from imbox.parser import parse_email

SMIME_CONTENT_TYPES = ('application/pkcs7-mime', 'application/x-pkcs7-mime')


class SmimeError(Exception):
    """
    Raised when S/MIME credentials cannot be loaded or a message cannot be decrypted.
    """


def is_encrypted(email_message):
    """
    Determine whether a parsed email.message.Message is an S/MIME encrypted (enveloped-data) message.
    """
    if email_message.get_content_type() not in SMIME_CONTENT_TYPES:
        return False
    smime_type = email_message.get_param('smime-type')
    if smime_type:
        return smime_type.lower() == 'enveloped-data'
    # Some clients omit smime-type, fall back to the conventional filename
    filename = email_message.get_param('name') or email_message.get_filename() or ''
    return filename.lower().endswith('.p7m')


class SmimeDecryptor:
    """
    Decrypts S/MIME encrypted messages using a private key and certificate.
    """

    def __init__(self, certificate, private_key):
        self.certificate = certificate
        self.private_key = private_key

    @staticmethod
    def load(key_path, cert_path=None, password=None):
        """
        Load credentials from either a PEM private key and PEM certificate, or a PKCS#12 (.p12/.pfx) bundle.
        """
        password_bytes = password.encode() if password else None
        try:
            with open(key_path, 'rb') as key_file:
                key_data = key_file.read()
        except OSError as ex:
            raise SmimeError(f'Unable to read S/MIME key file: {key_path}') from ex

        if b'-----BEGIN' in key_data:
            if not cert_path:
                raise SmimeError('--smime-cert is required when --smime-key is a PEM private key')
            try:
                private_key = load_pem_private_key(key_data, password_bytes)
                with open(cert_path, 'rb') as cert_file:
                    certificate = x509.load_pem_x509_certificate(cert_file.read())
            except (OSError, ValueError, TypeError) as ex:
                raise SmimeError(f'Unable to load S/MIME credentials: {ex}') from ex
            return SmimeDecryptor(certificate, private_key)

        try:
            private_key, certificate, _ = pkcs12.load_key_and_certificates(key_data, password_bytes)
            if cert_path:
                with open(cert_path, 'rb') as cert_file:
                    certificate = x509.load_pem_x509_certificate(cert_file.read())
        except (OSError, ValueError, TypeError) as ex:
            raise SmimeError(f'Unable to load S/MIME credentials: {ex}') from ex
        if private_key is None or certificate is None:
            raise SmimeError('PKCS#12 bundle must contain both a private key and a certificate')
        return SmimeDecryptor(certificate, private_key)

    def decrypt_message(self, message):
        """
        Given an imbox message, return a new imbox message with the decrypted content if the message is S/MIME
        encrypted. Unencrypted messages are returned unchanged.
        """
        email_message = email.message_from_string(message.raw_email, policy=compat32)
        if not is_encrypted(email_message):
            return message

        try:
            decrypted = pkcs7.pkcs7_decrypt_der(email_message.get_payload(decode=True), self.certificate,
                                                self.private_key, [])
        except ValueError as ex:
            raise SmimeError(f'Unable to decrypt S/MIME message: {ex}') from ex

        inner_message = email.message_from_bytes(decrypted, policy=compat32)
        # The encrypted entity only carries MIME headers, so carry the envelope headers (From, To, Subject, Date etc.)
        # across from the outer message
        inner_headers = {header.lower() for header in inner_message.keys()}
        for header, value in email_message.items():
            lower_header = header.lower()
            if lower_header.startswith('content-') or lower_header == 'mime-version' or lower_header in inner_headers:
                continue
            inner_message[header] = value
        if 'MIME-Version' not in inner_message:
            inner_message['MIME-Version'] = '1.0'

        return parse_email(inner_message.as_bytes())
