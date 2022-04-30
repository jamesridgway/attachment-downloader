import base64
import quopri
import re


class QuoPriEncoding:
    @staticmethod
    def decode(encoded_text):
        encoded_word_regex = r'=\?{1}(.+)\?{1}([B|Q|b|q])\?{1}(.+)\?{1}='
        matches = re.match(encoded_word_regex, encoded_text)
        if matches is None:
            return encoded_text
        charset, encoding, encoded_text = matches.groups()
        if encoding.upper() == 'B':
            byte_string = base64.b64decode(encoded_text)
        elif encoding.upper() == 'Q':
            byte_string = quopri.decodestring(encoded_text)
        return byte_string.decode(charset)
