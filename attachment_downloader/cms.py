"""
CMS (RFC 5652) parsing for S/MIME: extracting signed-data content, and decrypting enveloped-data and authenticated
enveloped-data (RFC 5083).

Supported algorithms:
* Key transport (RSA): RSAES-PKCS1-v1_5 and RSAES-OAEP (RFC 8017)
* Key agreement (EC): ECDH with the ANSI X9.63 KDF and AES key wrap (RFC 5753)
* Content encryption: AES-CBC and AES-GCM (RFC 5084)
"""
from contextlib import contextmanager
from dataclasses import dataclass

from cryptography import x509
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes, padding
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography.hazmat.primitives.asymmetric import padding as asymmetric_padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.x963kdf import X963KDF
from cryptography.hazmat.primitives.keywrap import InvalidUnwrap, aes_key_unwrap

from attachment_downloader.asn1 import (Asn1Error, Element, TAG_OCTET_STRING, TAG_SEQUENCE, decode, encode_explicit,
                                        encode_octet_string, encode_sequence, encode_set)

OID_SIGNED_DATA = '1.2.840.113549.1.7.2'
OID_ENVELOPED_DATA = '1.2.840.113549.1.7.3'
OID_AUTH_ENVELOPED_DATA = '1.2.840.113549.1.9.16.1.23'
ENCRYPTED_CONTENT_TYPES = (OID_ENVELOPED_DATA, OID_AUTH_ENVELOPED_DATA)

OID_RSA_ENCRYPTION = '1.2.840.113549.1.1.1'
OID_RSAES_OAEP = '1.2.840.113549.1.1.7'
OID_MGF1 = '1.2.840.113549.1.1.8'

HASHES = {
    '1.3.14.3.2.26': hashes.SHA1,
    '2.16.840.1.101.3.4.2.4': hashes.SHA224,
    '2.16.840.1.101.3.4.2.1': hashes.SHA256,
    '2.16.840.1.101.3.4.2.2': hashes.SHA384,
    '2.16.840.1.101.3.4.2.3': hashes.SHA512,
}

# The cofactor variants give the same result as the standard variants, as the supported curves have a cofactor of 1
ECDH_KDF_HASHES = {
    '1.3.133.16.840.63.0.2': hashes.SHA1,
    '1.3.132.1.11.0': hashes.SHA224,
    '1.3.132.1.11.1': hashes.SHA256,
    '1.3.132.1.11.2': hashes.SHA384,
    '1.3.132.1.11.3': hashes.SHA512,
    '1.3.133.16.840.63.0.3': hashes.SHA1,
    '1.3.132.1.14.0': hashes.SHA224,
    '1.3.132.1.14.1': hashes.SHA256,
    '1.3.132.1.14.2': hashes.SHA384,
    '1.3.132.1.14.3': hashes.SHA512,
}

AES_KEY_WRAP_KEY_SIZES = {
    '2.16.840.1.101.3.4.1.5': 16,
    '2.16.840.1.101.3.4.1.25': 24,
    '2.16.840.1.101.3.4.1.45': 32,
}
AES_CBC_KEY_SIZES = {
    '2.16.840.1.101.3.4.1.2': 16,
    '2.16.840.1.101.3.4.1.22': 24,
    '2.16.840.1.101.3.4.1.42': 32,
}
AES_GCM_KEY_SIZES = {
    '2.16.840.1.101.3.4.1.6': 16,
    '2.16.840.1.101.3.4.1.26': 24,
    '2.16.840.1.101.3.4.1.46': 32,
}
GCM_DEFAULT_ICV_LENGTH = 12

KEY_AGREE_RECIPIENT_INFO = 1
ORIGINATOR_PUBLIC_KEY = 1


class CmsError(Exception):
    """
    Raised when a CMS structure is invalid, unsupported or cannot be decrypted.
    """


@dataclass
class AlgorithmIdentifier:
    """
    An algorithm OID, its optional parameters and its encoding.
    """
    oid: str
    parameters: Element | None
    raw: bytes


@dataclass
class EncryptedContent:
    """
    Encrypted content, with the MAC and authenticated attributes of authenticated enveloped-data.
    """
    algorithm: AlgorithmIdentifier
    ciphertext: bytes
    mac: bytes | None = None
    authenticated_attributes: bytes = b''


def content_type(der_data):
    """
    The content type OID of a CMS ContentInfo.
    """
    with _parsing('ContentInfo'):
        return _content_info(der_data)[0]


def signed_content(der_data):
    """
    The encapsulated content of a signed-data ContentInfo. The signature is not verified.
    """
    with _parsing('signed-data'):
        _, signed_data = _content_info(der_data)
        encapsulated_content_info = signed_data.children()[2].children()
        content = _context(encapsulated_content_info, 0)
        if content is None:
            raise CmsError('CMS signed-data does not contain any content')
        return content.children()[0].octets()


def decrypt(der_data, certificate, private_key):
    """
    The decrypted content of an enveloped-data or authenticated enveloped-data ContentInfo.
    """
    with _parsing('enveloped-data'):
        content_type_oid, enveloped_data = _content_info(der_data)
        if content_type_oid not in ENCRYPTED_CONTENT_TYPES:
            raise CmsError(f'Unsupported CMS content type: {content_type_oid}')
        recipient_infos, encrypted_content = _enveloped_data(enveloped_data)
        content_key = _content_key(recipient_infos, certificate, private_key)
        return _decrypt_content(encrypted_content, content_key)


@contextmanager
def _parsing(structure):
    try:
        yield
    except (Asn1Error, IndexError, ValueError) as ex:
        raise CmsError(f'Invalid CMS {structure} structure') from ex


def _content_info(der_data):
    content_info = decode(der_data).children()
    return content_info[0].oid(), content_info[1].children()[0]


def _context(elements, tag_number):
    return next((element for element in elements if element.is_context(tag_number)), None)


def _algorithm(element):
    oid, *parameters = element.children()
    return AlgorithmIdentifier(oid.oid(), parameters[0] if parameters else None, element.raw)


def _enveloped_data(enveloped_data):
    fields = [field for field in enveloped_data.children() if not field.is_context(0)]
    _, recipient_infos, encrypted_content_info, *trailing_fields = fields

    _, algorithm, *ciphertext = encrypted_content_info.children()
    if not ciphertext:
        raise CmsError('CMS enveloped-data does not contain any content')
    encrypted_content = EncryptedContent(_algorithm(algorithm), ciphertext[0].octets())

    mac = next((field for field in trailing_fields if field.is_universal(TAG_OCTET_STRING)), None)
    if mac is not None:
        encrypted_content.mac = mac.octets()
        authenticated_attributes = _context(trailing_fields, 1)
        if authenticated_attributes is not None:
            encrypted_content.authenticated_attributes = encode_set(authenticated_attributes.content)

    return recipient_infos.children(), encrypted_content


def _content_key(recipient_infos, certificate, private_key):
    for recipient_info in recipient_infos:
        if recipient_info.is_universal(TAG_SEQUENCE):
            _, recipient_id, algorithm, encrypted_key = recipient_info.children()
            if _is_recipient(recipient_id, certificate):
                return _decrypt_transported_key(_algorithm(algorithm), encrypted_key.octets(), private_key)
        elif recipient_info.is_context(KEY_AGREE_RECIPIENT_INFO):
            fields = recipient_info.children()
            for recipient_encrypted_key in fields[-1].children():
                recipient_id, encrypted_key = recipient_encrypted_key.children()
                if recipient_id.is_context(0):
                    recipient_id = recipient_id.children()[0]
                if _is_recipient(recipient_id, certificate):
                    return _decrypt_agreed_key(fields, encrypted_key.octets(), private_key)
    raise CmsError('Message is not encrypted for the provided certificate')


def _is_recipient(recipient_id, certificate):
    if recipient_id.is_universal(TAG_SEQUENCE):
        issuer, serial_number = recipient_id.children()
        return issuer.raw == certificate.issuer.public_bytes() and serial_number.integer() == certificate.serial_number
    try:
        subject_key_identifier = certificate.extensions.get_extension_for_class(x509.SubjectKeyIdentifier)
    except x509.ExtensionNotFound:
        return False
    return recipient_id.octets() == subject_key_identifier.value.digest


def _decrypt_transported_key(algorithm, encrypted_key, private_key):
    if not isinstance(private_key, rsa.RSAPrivateKey):
        raise CmsError('An RSA private key is required to decrypt this message')
    if algorithm.oid == OID_RSA_ENCRYPTION:
        key_padding = asymmetric_padding.PKCS1v15()
    elif algorithm.oid == OID_RSAES_OAEP:
        key_padding = _oaep_padding(algorithm.parameters.children() if algorithm.parameters else [])
    else:
        raise CmsError(f'Unsupported key transport algorithm: {algorithm.oid}')

    try:
        return private_key.decrypt(encrypted_key, key_padding)
    except ValueError as ex:
        raise CmsError('Unable to decrypt the content encryption key') from ex


def _oaep_padding(parameters):
    hash_algorithm, mask_generation, label_source = (_context(parameters, tag_number) for tag_number in range(3))

    hash_function = _hash(_algorithm(hash_algorithm.children()[0]).oid) if hash_algorithm else hashes.SHA1()
    mask_hash_function = hashes.SHA1()
    if mask_generation:
        mask_generation_function = _algorithm(mask_generation.children()[0])
        if mask_generation_function.oid != OID_MGF1:
            raise CmsError(f'Unsupported OAEP mask generation function: {mask_generation_function.oid}')
        mask_hash_function = _hash(_algorithm(mask_generation_function.parameters).oid)
    label = _algorithm(label_source.children()[0]).parameters.octets() if label_source else None

    return asymmetric_padding.OAEP(mgf=asymmetric_padding.MGF1(mask_hash_function), algorithm=hash_function,
                                   label=label or None)


def _hash(oid):
    if oid not in HASHES:
        raise CmsError(f'Unsupported hash algorithm: {oid}')
    return HASHES[oid]()


def _decrypt_agreed_key(key_agree_recipient_info, encrypted_key, private_key):
    if not isinstance(private_key, ec.EllipticCurvePrivateKey):
        raise CmsError('An EC private key is required to decrypt this message')

    originator = key_agree_recipient_info[1].children()[0]
    if not originator.is_context(ORIGINATOR_PUBLIC_KEY):
        raise CmsError('Only ephemeral-static ECDH key agreement is supported')
    _, originator_public_key = originator.children()
    user_keying_material = _context(key_agree_recipient_info, 1)
    algorithm = _algorithm(key_agree_recipient_info[-2])

    if algorithm.oid not in ECDH_KDF_HASHES:
        raise CmsError(f'Unsupported key agreement algorithm: {algorithm.oid}')
    key_wrap_algorithm = _algorithm(algorithm.parameters)
    if key_wrap_algorithm.oid not in AES_KEY_WRAP_KEY_SIZES:
        raise CmsError(f'Unsupported key wrap algorithm: {key_wrap_algorithm.oid}')
    key_wrap_key_size = AES_KEY_WRAP_KEY_SIZES[key_wrap_algorithm.oid]

    originator_key = ec.EllipticCurvePublicKey.from_encoded_point(private_key.curve,
                                                                  originator_public_key.bit_string())
    shared_info = _ecc_cms_shared_info(key_wrap_algorithm,
                                       user_keying_material.children()[0].octets() if user_keying_material else None,
                                       key_wrap_key_size)
    key_encryption_key = X963KDF(algorithm=ECDH_KDF_HASHES[algorithm.oid](), length=key_wrap_key_size,
                                 sharedinfo=shared_info).derive(private_key.exchange(ec.ECDH(), originator_key))
    try:
        return aes_key_unwrap(key_encryption_key, encrypted_key)
    except InvalidUnwrap as ex:
        raise CmsError('Unable to decrypt the content encryption key') from ex


def _ecc_cms_shared_info(key_wrap_algorithm, user_keying_material, key_wrap_key_size):
    entity_u_info = b''
    if user_keying_material is not None:
        entity_u_info = encode_explicit(0, encode_octet_string(user_keying_material))
    supp_pub_info = encode_explicit(2, encode_octet_string((key_wrap_key_size * 8).to_bytes(4, 'big')))
    return encode_sequence(key_wrap_algorithm.raw + entity_u_info + supp_pub_info)


def _decrypt_content(encrypted_content, content_key):
    if encrypted_content.mac is None:
        return _decrypt_aes_cbc(encrypted_content, content_key)
    return _decrypt_aes_gcm(encrypted_content, content_key)


def _decrypt_aes_cbc(encrypted_content, content_key):
    algorithm = encrypted_content.algorithm
    _check_key_size(algorithm, AES_CBC_KEY_SIZES, content_key)

    decryptor = Cipher(algorithms.AES(content_key), modes.CBC(algorithm.parameters.octets())).decryptor()
    unpadder = padding.PKCS7(algorithms.AES.block_size).unpadder()
    try:
        padded = decryptor.update(encrypted_content.ciphertext) + decryptor.finalize()
        return unpadder.update(padded) + unpadder.finalize()
    except ValueError as ex:
        raise CmsError('Unable to decrypt content') from ex


def _decrypt_aes_gcm(encrypted_content, content_key):
    algorithm = encrypted_content.algorithm
    _check_key_size(algorithm, AES_GCM_KEY_SIZES, content_key)

    nonce, *icv_length = algorithm.parameters.children()
    expected_mac_length = icv_length[0].integer() if icv_length else GCM_DEFAULT_ICV_LENGTH
    mac = encrypted_content.mac
    if len(mac) != expected_mac_length:
        raise CmsError('CMS authenticated enveloped-data MAC length does not match its parameters')

    try:
        decryptor = Cipher(algorithms.AES(content_key), modes.GCM(nonce.octets(), mac, min_tag_length=len(mac))) \
            .decryptor()
        decryptor.authenticate_additional_data(encrypted_content.authenticated_attributes)
        return decryptor.update(encrypted_content.ciphertext) + decryptor.finalize()
    except (InvalidTag, ValueError) as ex:
        raise CmsError('Unable to decrypt content, the message may have been tampered with') from ex


def _check_key_size(algorithm, key_sizes, content_key):
    if algorithm.oid not in key_sizes:
        raise CmsError(f'Unsupported content encryption algorithm: {algorithm.oid}')
    if len(content_key) != key_sizes[algorithm.oid]:
        raise CmsError('Content encryption key has the wrong length')
