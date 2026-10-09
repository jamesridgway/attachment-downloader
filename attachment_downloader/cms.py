"""
CMS (RFC 5652) decryption of enveloped-data and authenticated enveloped-data (RFC 5083) structures.

Supported algorithms:
* Key transport (RSA): RSAES-PKCS1-v1_5 and RSAES-OAEP (RFC 8017)
* Key agreement (EC): ECDH with the ANSI X9.63 KDF and AES key wrap (RFC 5753)
* Content encryption: AES-CBC and AES-GCM (RFC 5084)
"""
from cryptography import x509
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes, padding
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography.hazmat.primitives.asymmetric import padding as asymmetric_padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.x963kdf import X963KDF
from cryptography.hazmat.primitives.keywrap import InvalidUnwrap, aes_key_unwrap

from attachment_downloader.asn1 import Asn1Error, TAG_CLASS_UNIVERSAL, TAG_OCTET_STRING, decode, encode

OID_ENVELOPED_DATA = '1.2.840.113549.1.7.3'
OID_AUTH_ENVELOPED_DATA = '1.2.840.113549.1.9.16.1.23'

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

# dhSinglePass-stdDH-*kdf-scheme and dhSinglePass-cofactorDH-*kdf-scheme (RFC 5753). The cofactor variants give the
# same result for the prime curves supported here, which all have a cofactor of 1.
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

# Key sizes in bytes
AES_KEY_WRAP = {
    '2.16.840.1.101.3.4.1.5': 16,
    '2.16.840.1.101.3.4.1.25': 24,
    '2.16.840.1.101.3.4.1.45': 32,
}
AES_CBC = {
    '2.16.840.1.101.3.4.1.2': 16,
    '2.16.840.1.101.3.4.1.22': 24,
    '2.16.840.1.101.3.4.1.42': 32,
}
AES_GCM = {
    '2.16.840.1.101.3.4.1.6': 16,
    '2.16.840.1.101.3.4.1.26': 24,
    '2.16.840.1.101.3.4.1.46': 32,
}

GCM_DEFAULT_ICV_LENGTH = 12


class CmsError(Exception):
    """
    Raised when a CMS structure cannot be decrypted.
    """


def decrypt(der_data, certificate, private_key):
    """
    Decrypt a CMS ContentInfo containing enveloped-data or authenticated enveloped-data, returning the content.
    """
    try:
        content_info = decode(der_data).children()
        content_type = content_info[0].oid()
        fields = content_info[1].children()[0].children()
        if content_type not in (OID_ENVELOPED_DATA, OID_AUTH_ENVELOPED_DATA):
            raise CmsError(f'Unsupported CMS content type: {content_type}')

        # Skip version and the optional [0] originatorInfo
        index = 2 if fields[1].is_context(0) else 1
        recipient_infos = fields[index].children()
        encrypted_content_info = fields[index + 1].children()

        content_key = _decrypt_content_key(recipient_infos, certificate, private_key)

        if content_type == OID_AUTH_ENVELOPED_DATA:
            auth_attrs = next((field for field in fields[index + 2:] if field.is_context(1)), None)
            mac = next(field for field in fields[index + 2:]
                       if field.tag_class == TAG_CLASS_UNIVERSAL and field.tag_number == TAG_OCTET_STRING)
            # The authenticated attributes are authenticated with their SET OF tag rather than the IMPLICIT [1] tag
            aad = b'\x31' + auth_attrs.raw[1:] if auth_attrs else b''
            return _decrypt_auth_content(encrypted_content_info, content_key, mac.octets(), aad)
        return _decrypt_content(encrypted_content_info, content_key)
    except (Asn1Error, IndexError, StopIteration) as ex:
        raise CmsError('Invalid CMS enveloped-data structure') from ex


def _decrypt_content_key(recipient_infos, certificate, private_key):
    for recipient_info in recipient_infos:
        if recipient_info.tag_class == TAG_CLASS_UNIVERSAL:
            # KeyTransRecipientInfo
            fields = recipient_info.children()
            if _matches_recipient(fields[1], certificate):
                return _decrypt_key_transport(fields[2], fields[3].octets(), private_key)
        elif recipient_info.is_context(1):
            # KeyAgreeRecipientInfo
            fields = recipient_info.children()
            for recipient_encrypted_key in fields[-1].children():
                rid, encrypted_key = recipient_encrypted_key.children()
                if _matches_recipient(rid, certificate):
                    return _decrypt_key_agreement(fields, encrypted_key.octets(), private_key)
    raise CmsError('Message is not encrypted for the provided certificate')


def _matches_recipient(rid, certificate):
    if rid.tag_class == TAG_CLASS_UNIVERSAL:
        # IssuerAndSerialNumber
        issuer, serial = rid.children()
        return issuer.raw == certificate.issuer.public_bytes() and serial.integer() == certificate.serial_number
    if rid.is_context(0):
        # SubjectKeyIdentifier, or RecipientKeyIdentifier for key agreement
        key_identifier = rid.octets() if not rid.constructed else rid.children()[0].octets()
        try:
            extension = certificate.extensions.get_extension_for_class(x509.SubjectKeyIdentifier)
        except x509.ExtensionNotFound:
            return False
        return extension.value.digest == key_identifier
    return False


def _decrypt_key_transport(algorithm, encrypted_key, private_key):
    if not isinstance(private_key, rsa.RSAPrivateKey):
        raise CmsError('An RSA private key is required to decrypt this message')

    algorithm_fields = algorithm.children()
    algorithm_oid = algorithm_fields[0].oid()
    if algorithm_oid == OID_RSA_ENCRYPTION:
        key_padding = asymmetric_padding.PKCS1v15()
    elif algorithm_oid == OID_RSAES_OAEP:
        key_padding = _oaep_padding(algorithm_fields[1].children() if len(algorithm_fields) > 1 else [])
    else:
        raise CmsError(f'Unsupported key transport algorithm: {algorithm_oid}')

    try:
        return private_key.decrypt(encrypted_key, key_padding)
    except ValueError as ex:
        raise CmsError('Unable to decrypt the content encryption key') from ex


def _oaep_padding(parameters):
    # RSAES-OAEP-params, every field is optional and defaults to SHA-1 with an empty label
    hash_algorithm = hashes.SHA1()
    mgf_hash_algorithm = hashes.SHA1()
    label = None
    for parameter in parameters:
        algorithm = parameter.children()[0].children()
        if parameter.is_context(0):
            hash_algorithm = _hash(algorithm[0].oid())
        elif parameter.is_context(1):
            if algorithm[0].oid() != OID_MGF1:
                raise CmsError(f'Unsupported OAEP mask generation function: {algorithm[0].oid()}')
            mgf_hash_algorithm = _hash(algorithm[1].children()[0].oid())
        elif parameter.is_context(2):
            label = algorithm[1].octets() or None
    return asymmetric_padding.OAEP(mgf=asymmetric_padding.MGF1(mgf_hash_algorithm), algorithm=hash_algorithm,
                                   label=label)


def _hash(oid):
    if oid not in HASHES:
        raise CmsError(f'Unsupported hash algorithm: {oid}')
    return HASHES[oid]()


def _decrypt_key_agreement(fields, encrypted_key, private_key):
    if not isinstance(private_key, ec.EllipticCurvePrivateKey):
        raise CmsError('An EC private key is required to decrypt this message')

    # Skip version, the remaining fields are originator, optional [1] ukm, keyEncryptionAlgorithm and
    # recipientEncryptedKeys
    originator = fields[1].children()[0]
    ukm = fields[2].children()[0].octets() if fields[2].is_context(1) else None
    key_encryption_algorithm = fields[-2].children()

    if not originator.is_context(1):
        raise CmsError('Only ephemeral-static ECDH key agreement is supported')
    # The public key is a BIT STRING, whose first content octet is the number of unused bits
    originator_key = ec.EllipticCurvePublicKey.from_encoded_point(private_key.curve,
                                                                  originator.children()[1].content[1:])

    kdf_oid = key_encryption_algorithm[0].oid()
    if kdf_oid not in ECDH_KDF_HASHES:
        raise CmsError(f'Unsupported key agreement algorithm: {kdf_oid}')
    key_wrap_algorithm = key_encryption_algorithm[1]
    key_wrap_oid = key_wrap_algorithm.children()[0].oid()
    if key_wrap_oid not in AES_KEY_WRAP:
        raise CmsError(f'Unsupported key wrap algorithm: {key_wrap_oid}')
    key_wrap_length = AES_KEY_WRAP[key_wrap_oid]

    shared_secret = private_key.exchange(ec.ECDH(), originator_key)
    key_encryption_key = X963KDF(algorithm=ECDH_KDF_HASHES[kdf_oid](), length=key_wrap_length,
                                 sharedinfo=_ecc_cms_shared_info(key_wrap_algorithm.raw, ukm, key_wrap_length)) \
        .derive(shared_secret)
    try:
        return aes_key_unwrap(key_encryption_key, encrypted_key)
    except InvalidUnwrap as ex:
        raise CmsError('Unable to decrypt the content encryption key') from ex


def _ecc_cms_shared_info(key_wrap_algorithm, ukm, key_wrap_length):
    """
    DER encoded ECC-CMS-SharedInfo (RFC 5753 section 7.2), used as the KDF shared info.
    """
    shared_info = key_wrap_algorithm
    if ukm is not None:
        shared_info += encode(0xa0, encode(0x04, ukm))
    shared_info += encode(0xa2, encode(0x04, (key_wrap_length * 8).to_bytes(4, 'big')))
    return encode(0x30, shared_info)


def _encrypted_content(encrypted_content_info):
    content_encryption_algorithm = encrypted_content_info[1].children()
    if len(encrypted_content_info) < 3:
        raise CmsError('CMS enveloped-data does not contain any content')
    return content_encryption_algorithm, encrypted_content_info[2].octets()


def _decrypt_content(encrypted_content_info, content_key):
    algorithm, ciphertext = _encrypted_content(encrypted_content_info)
    algorithm_oid = algorithm[0].oid()
    if algorithm_oid not in AES_CBC:
        raise CmsError(f'Unsupported content encryption algorithm: {algorithm_oid}')
    _check_key_length(content_key, AES_CBC[algorithm_oid])

    decryptor = Cipher(algorithms.AES(content_key), modes.CBC(algorithm[1].octets())).decryptor()
    unpadder = padding.PKCS7(algorithms.AES.block_size).unpadder()
    try:
        padded = decryptor.update(ciphertext) + decryptor.finalize()
        return unpadder.update(padded) + unpadder.finalize()
    except ValueError as ex:
        raise CmsError('Unable to decrypt content') from ex


def _decrypt_auth_content(encrypted_content_info, content_key, mac, aad):
    algorithm, ciphertext = _encrypted_content(encrypted_content_info)
    algorithm_oid = algorithm[0].oid()
    if algorithm_oid not in AES_GCM:
        raise CmsError(f'Unsupported authenticated content encryption algorithm: {algorithm_oid}')
    _check_key_length(content_key, AES_GCM[algorithm_oid])

    gcm_parameters = algorithm[1].children()
    nonce = gcm_parameters[0].octets()
    icv_length = gcm_parameters[1].integer() if len(gcm_parameters) > 1 else GCM_DEFAULT_ICV_LENGTH
    if len(mac) != icv_length:
        raise CmsError('CMS authenticated enveloped-data MAC length does not match its parameters')

    try:
        decryptor = Cipher(algorithms.AES(content_key), modes.GCM(nonce, mac, min_tag_length=len(mac))).decryptor()
        decryptor.authenticate_additional_data(aad)
        return decryptor.update(ciphertext) + decryptor.finalize()
    except (InvalidTag, ValueError) as ex:
        raise CmsError('Unable to decrypt content, the message may have been tampered with') from ex


def _check_key_length(content_key, expected_length):
    if len(content_key) != expected_length:
        raise CmsError('Content encryption key has the wrong length')
