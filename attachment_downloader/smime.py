"""
S/MIME support: removing the opaque signed and encrypted layers of a message so that its attachments can be read.
"""
import email
import logging
from email.policy import compat32

from cryptography import x509
from cryptography.hazmat.primitives.serialization import load_pem_private_key, pkcs12
from imbox.parser import parse_email

from attachment_downloader import cms

SMIME_CONTENT_TYPES = ('application/pkcs7-mime', 'application/x-pkcs7-mime')
MAX_NESTING = 5


class SmimeError(Exception):
    """
    Raised when S/MIME credentials cannot be loaded or a message cannot be decrypted or unwrapped.
    """


def unwrap_message(message, decryptor=None):
    """
    Given an imbox message, return a new imbox message with any S/MIME opaque signed or encrypted layers removed so
    that the attachments within are accessible. Other messages are returned unchanged.

    Encrypted messages are only decrypted when a decryptor is provided.
    """
    if not _has_smime_content_type(message):
        return message

    outer_message = email.message_from_string(message.raw_email, policy=compat32)
    try:
        inner_message = _unwrap(outer_message, decryptor)
    except cms.CmsError as ex:
        raise SmimeError(str(ex)) from ex

    if inner_message is outer_message:
        return message

    _copy_envelope_headers(outer_message, inner_message)
    return parse_email(inner_message.as_bytes())


def _has_smime_content_type(message):
    return any(header['Name'].lower() == 'content-type' and 'pkcs7-mime' in header['Value'].lower()
               for header in getattr(message, 'headers', []))


def _unwrap(email_message, decryptor):
    for _ in range(MAX_NESTING):
        if email_message.get_content_type() not in SMIME_CONTENT_TYPES:
            return email_message
        content = _open(_payload(email_message), decryptor)
        if content is None:
            return email_message
        email_message = email.message_from_bytes(content, policy=compat32)
    raise SmimeError(f'S/MIME message is nested more than {MAX_NESTING} levels deep')


def _payload(email_message):
    return email_message.get_payload(decode=True) or b''


def _open(der_data, decryptor):
    content_type = cms.content_type(der_data)
    if content_type == cms.OID_SIGNED_DATA:
        return cms.signed_content(der_data)
    if content_type in cms.ENCRYPTED_CONTENT_TYPES:
        if decryptor is None:
            logging.warning('Message is S/MIME encrypted, but no S/MIME key was provided to decrypt it')
            return None
        return decryptor.decrypt(der_data)
    raise SmimeError(f'Unsupported S/MIME content type: {content_type}')


def _copy_envelope_headers(outer_message, inner_message):
    inner_headers = {header.lower() for header in inner_message.keys()}
    for header, value in outer_message.items():
        lower_header = header.lower()
        if lower_header.startswith('content-') or lower_header == 'mime-version' or lower_header in inner_headers:
            continue
        inner_message[header] = value
    if 'MIME-Version' not in inner_message:
        inner_message['MIME-Version'] = '1.0'


class SmimeDecryptor:
    """
    Decrypts S/MIME encrypted content using a private key and certificate.
    """

    def __init__(self, certificate, private_key):
        self.certificate = certificate
        self.private_key = private_key

    @staticmethod
    def load(key_path, cert_path=None, password=None):
        """
        Load credentials from either a PEM private key and PEM certificate, or a PKCS#12 (.p12/.pfx) bundle.
        """
        key_data = _read(key_path)
        password_bytes = password.encode() if password else None
        try:
            if b'-----BEGIN' in key_data:
                if not cert_path:
                    raise SmimeError('A certificate is required when the private key is in PEM format')
                private_key = load_pem_private_key(key_data, password_bytes)
                certificate = None
            else:
                private_key, certificate, _ = pkcs12.load_key_and_certificates(key_data, password_bytes)
            if cert_path:
                certificate = x509.load_pem_x509_certificate(_read(cert_path))
        except (ValueError, TypeError) as ex:
            raise SmimeError(f'Unable to load S/MIME credentials: {ex}') from ex

        if private_key is None or certificate is None:
            raise SmimeError('PKCS#12 bundle must contain both a private key and a certificate')
        return SmimeDecryptor(certificate, private_key)

    def decrypt(self, der_data):
        """
        Decrypt an enveloped-data or authenticated enveloped-data CMS structure, returning the decrypted content.
        """
        return cms.decrypt(der_data, self.certificate, self.private_key)


def _read(path):
    try:
        with open(path, 'rb') as file:
            return file.read()
    except OSError as ex:
        raise SmimeError(f'Unable to read S/MIME credentials file: {path}') from ex
