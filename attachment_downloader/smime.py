"""
S/MIME support: unwrapping opaque signed messages and decrypting encrypted messages.
"""
import email
import logging
from email.policy import compat32

from cryptography import x509
from cryptography.hazmat.primitives.serialization import load_pem_private_key, pkcs12
from imbox.parser import parse_email

from attachment_downloader import cms
from attachment_downloader.asn1 import Asn1Error, decode

SMIME_CONTENT_TYPES = ('application/pkcs7-mime', 'application/x-pkcs7-mime')

OID_SIGNED_DATA = '1.2.840.113549.1.7.2'
ENCRYPTED_CONTENT_TYPES = (cms.OID_ENVELOPED_DATA, cms.OID_AUTH_ENVELOPED_DATA)

# Guards against maliciously deep nesting of signed/encrypted layers
MAX_NESTING = 5


class SmimeError(Exception):
    """
    Raised when S/MIME credentials cannot be loaded or a message cannot be decrypted or unwrapped.
    """


def cms_content_type(email_message):
    """
    The CMS content type OID of an S/MIME (application/pkcs7-mime) email.message.Message, or None if the message is
    not an S/MIME message.
    """
    if email_message.get_content_type() not in SMIME_CONTENT_TYPES:
        return None
    try:
        return decode(email_message.get_payload(decode=True)).children()[0].oid()
    except (Asn1Error, IndexError, TypeError) as ex:
        raise SmimeError('Invalid S/MIME message structure') from ex


def is_encrypted(email_message):
    """
    Determine whether a parsed email.message.Message is an S/MIME encrypted (enveloped-data or authenticated
    enveloped-data) message.
    """
    return cms_content_type(email_message) in ENCRYPTED_CONTENT_TYPES


def signed_content(der_data):
    """
    Extract the encapsulated content from an opaque signed (signed-data) CMS structure.

    The signature is not verified.
    """
    try:
        signed_data = decode(der_data).children()[1].children()[0]
        encap_content_info = signed_data.children()[2].children()
    except (Asn1Error, IndexError) as ex:
        raise SmimeError('Invalid S/MIME signed-data structure') from ex
    if len(encap_content_info) < 2:
        raise SmimeError('S/MIME signed-data does not contain any content')
    try:
        return encap_content_info[1].children()[0].octets()
    except (Asn1Error, IndexError) as ex:
        raise SmimeError('Invalid S/MIME signed-data structure') from ex


def unwrap_message(message, decryptor=None):
    """
    Given an imbox message, return a new imbox message with any S/MIME opaque signed or encrypted layers removed so
    that the attachments within are accessible. Other messages are returned unchanged.

    Encrypted messages are only decrypted when a decryptor is provided.
    """
    if not _has_smime_content_type(message):
        return message

    outer_message = email.message_from_string(message.raw_email, policy=compat32)
    inner_message = outer_message
    for _ in range(MAX_NESTING):
        content_type = cms_content_type(inner_message)
        if content_type == OID_SIGNED_DATA:
            content = signed_content(inner_message.get_payload(decode=True))
        elif content_type in ENCRYPTED_CONTENT_TYPES:
            if decryptor is None:
                logging.warning("Message '%s' is S/MIME encrypted, provide --smime-key to decrypt it",
                                getattr(message, 'message_id', ''))
                break
            content = decryptor.decrypt(inner_message.get_payload(decode=True))
        elif content_type is None:
            break
        else:
            raise SmimeError(f'Unsupported S/MIME content type: {content_type}')
        inner_message = email.message_from_bytes(content, policy=compat32)
    else:
        raise SmimeError(f'S/MIME message is nested more than {MAX_NESTING} levels deep')

    if inner_message is outer_message:
        return message

    # The signed/encrypted entity only carries MIME headers, so carry the envelope headers (From, To, Subject, Date
    # etc.) across from the outer message
    inner_headers = {header.lower() for header in inner_message.keys()}
    for header, value in outer_message.items():
        lower_header = header.lower()
        if lower_header.startswith('content-') or lower_header == 'mime-version' or lower_header in inner_headers:
            continue
        inner_message[header] = value
    if 'MIME-Version' not in inner_message:
        inner_message['MIME-Version'] = '1.0'

    return parse_email(inner_message.as_bytes())


def _has_smime_content_type(message):
    """
    Cheap check against the headers imbox has already parsed, to avoid re-parsing every message.
    """
    for header in getattr(message, 'headers', []):
        if header['Name'].lower() == 'content-type' and 'pkcs7-mime' in header['Value'].lower():
            return True
    return False


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

    def decrypt(self, der_data):
        """
        Decrypt an enveloped-data or authenticated enveloped-data CMS structure, returning the decrypted content.
        """
        try:
            return cms.decrypt(der_data, self.certificate, self.private_key)
        except cms.CmsError as ex:
            raise SmimeError(f'Unable to decrypt S/MIME message: {ex}') from ex
