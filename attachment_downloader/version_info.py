"""
Version.
"""
import platform
import sys
from importlib import metadata


class Version:
    """
    Version information.
    """
    @staticmethod
    def get():
        """
        The installed version number.
        """
        try:
            return metadata.version('attachment-downloader')
        except metadata.PackageNotFoundError:
            return 'unknown'

    @staticmethod
    def get_env_info():
        """
        Get environment information.
        """
        os_info = f"Release: {platform.release()}, Platform: {platform.platform()}"
        return f"(Python: {platform.python_version()}), OS: ({os_info}). Default Encoding: {sys.getdefaultencoding()}"
