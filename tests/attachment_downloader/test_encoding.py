from assertpy import assert_that

from attachment_downloader.encoding import QuoPriEncoding


class TestQuoPriEncoding:
    def test_decode(self):
        assert_that(QuoPriEncoding.decode('=?utf-8?b?2LPZhNin2YU=?=')).is_equal_to('سلام')
        assert_that(QuoPriEncoding.decode('=?UTF-8?B?2LPZhNin2YU=?=')).is_equal_to('سلام')
        assert_that(QuoPriEncoding.decode('Hello')).is_equal_to('Hello')
