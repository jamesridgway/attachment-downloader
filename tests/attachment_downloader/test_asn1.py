from assertpy import assert_that

from attachment_downloader.asn1 import (Asn1Error, decode, encode_explicit, encode_octet_string, encode_sequence,
                                        encode_set)


class TestAsn1:
    def test_decode_sequence(self):
        element = decode(bytes.fromhex('3008020101040361626300'))
        assert_that(element.constructed).is_true()
        assert_that(element.tag_number).is_equal_to(16)
        children = element.children()
        assert_that(children[0].integer()).is_equal_to(1)
        assert_that(children[1].octets()).is_equal_to(b'abc')

    def test_decode_long_form_length(self):
        element = decode(bytes.fromhex('048200c8') + b'a' * 200)
        assert_that(element.octets()).is_equal_to(b'a' * 200)

    def test_decode_oid(self):
        assert_that(decode(bytes.fromhex('06092a864886f70d010702')).oid()).is_equal_to('1.2.840.113549.1.7.2')
        assert_that(decode(bytes.fromhex('060b2a864886f70d0109100117')).oid()) \
            .is_equal_to('1.2.840.113549.1.9.16.1.23')

    def test_decode_indefinite_length_and_constructed_octet_string(self):
        # SEQUENCE (indefinite) { [0] (indefinite) { OCTET STRING (constructed, indefinite) { "ab", "cd" } } }
        element = decode(bytes.fromhex('3080a0802480040261620402636400000000' + '0000'))
        context = element.children()[0]
        assert_that(context.is_context(0)).is_true()
        assert_that(context.children()[0].octets()).is_equal_to(b'abcd')

    def test_decode_negative_integer(self):
        assert_that(decode(bytes.fromhex('0201ff')).integer()).is_equal_to(-1)

    def test_decode_truncated(self):
        assert_that(decode).raises(Asn1Error).when_called_with(bytes.fromhex('0405616263'))
        assert_that(decode).raises(Asn1Error).when_called_with(bytes.fromhex('3080020101'))
        assert_that(decode).raises(Asn1Error).when_called_with(b'')

    def test_oid_wrong_type(self):
        assert_that(decode(bytes.fromhex('020101')).oid).raises(Asn1Error).when_called_with()

    def test_encode(self):
        assert_that(encode_octet_string(b'abc')).is_equal_to(bytes.fromhex('0403616263'))
        assert_that(encode_sequence(encode_octet_string(b''))).is_equal_to(bytes.fromhex('30020400'))
        assert_that(encode_set(b'')).is_equal_to(bytes.fromhex('3100'))
        assert_that(encode_explicit(2, encode_octet_string(b''))).is_equal_to(bytes.fromhex('a2020400'))

    def test_encode_long_form_length(self):
        encoded = encode_octet_string(b'a' * 200)
        assert_that(encoded[:3]).is_equal_to(bytes.fromhex('0481c8'))
        assert_that(decode(encoded).octets()).is_equal_to(b'a' * 200)
