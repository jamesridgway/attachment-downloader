from assertpy import assert_that

from attachment_downloader.asn1 import Asn1Error, decode


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
