"""
Minimal ASN.1 BER/DER reader, sufficient for parsing the CMS (PKCS#7) structures used by S/MIME.
"""

TAG_CLASS_UNIVERSAL = 0
TAG_CLASS_CONTEXT = 2

TAG_INTEGER = 2
TAG_OCTET_STRING = 4
TAG_OID = 6


class Asn1Error(ValueError):
    """
    Raised when data is not valid BER/DER.
    """


class Element:
    """
    A decoded ASN.1 element.
    """

    def __init__(self, identifier, tag_number, content, raw):
        self.tag_class = identifier >> 6
        self.constructed = bool(identifier & 0x20)
        self.tag_number = tag_number
        self.content = content
        self.raw = raw

    def children(self):
        """
        Decode the content of a constructed element into its child elements.
        """
        if not self.constructed:
            raise Asn1Error('Element is not constructed')
        children = []
        offset = 0
        while offset < len(self.content):
            child, offset = read_element(self.content, offset)
            children.append(child)
        return children

    def is_context(self, tag_number):
        """
        Whether this is a context-specific element ([n]) with the given tag number.
        """
        return self.tag_class == TAG_CLASS_CONTEXT and self.tag_number == tag_number

    def octets(self):
        """
        Value of an OCTET STRING (or implicitly tagged OCTET STRING), including BER constructed encodings.
        """
        if self.constructed:
            return b''.join(child.octets() for child in self.children())
        return self.content

    def integer(self):
        """
        Value of an INTEGER.
        """
        return int.from_bytes(self.content, 'big', signed=True)

    def oid(self):
        """
        Value of an OBJECT IDENTIFIER in dotted notation.
        """
        if self.tag_class != TAG_CLASS_UNIVERSAL or self.tag_number != TAG_OID or not self.content:
            raise Asn1Error('Element is not an OBJECT IDENTIFIER')
        arcs = []
        value = 0
        for byte in self.content:
            value = (value << 7) | (byte & 0x7f)
            if not byte & 0x80:
                arcs.append(value)
                value = 0
        first = min(arcs[0] // 40, 2)
        return '.'.join(str(arc) for arc in [first, arcs[0] - first * 40] + arcs[1:])


def decode(data):
    """
    Decode a single ASN.1 element from the start of data.
    """
    element, _ = read_element(data, 0)
    return element


def read_element(data, offset):
    """
    Read the element starting at offset, returning the element and the offset of the following element.
    """
    start = offset
    identifier = _byte(data, offset)
    offset += 1
    constructed = bool(identifier & 0x20)
    tag_number = identifier & 0x1f
    if tag_number == 0x1f:
        tag_number = 0
        while True:
            byte = _byte(data, offset)
            offset += 1
            tag_number = (tag_number << 7) | (byte & 0x7f)
            if not byte & 0x80:
                break

    length = _byte(data, offset)
    offset += 1
    if length == 0x80:
        # BER indefinite length, content runs until the end-of-contents marker
        if not constructed:
            raise Asn1Error('Indefinite length used for primitive element')
        content_start = offset
        while data[offset:offset + 2] != b'\x00\x00':
            _, offset = read_element(data, offset)
        content = data[content_start:offset]
        offset += 2
    else:
        if length & 0x80:
            num_bytes = length & 0x7f
            if offset + num_bytes > len(data):
                raise Asn1Error('Truncated length')
            length = int.from_bytes(data[offset:offset + num_bytes], 'big')
            offset += num_bytes
        if offset + length > len(data):
            raise Asn1Error('Truncated content')
        content = data[offset:offset + length]
        offset += length

    return Element(identifier, tag_number, content, data[start:offset]), offset


def _byte(data, offset):
    if offset >= len(data):
        raise Asn1Error('Unexpected end of data')
    return data[offset]
