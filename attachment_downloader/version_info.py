"""
Version.
"""
import os
import platform
import subprocess
import sys

VERSION_FILENAME = os.path.abspath(os.path.join(os.path.dirname(__file__), 'version.py'))


class Version:
    """
    Version information.
    """
    @staticmethod
    def generate():
        """
        Generation version.py version information module
        """
        with subprocess.Popen(["git", "describe", "--always", "--tags"],
                              stdout=subprocess.PIPE,
                              stderr=None) as process:
            last_tag = process.communicate()[0].decode('ascii').strip()
            version = last_tag.split('-g', maxsplit=1)[0].replace('-', '.') if '-g' in last_tag else last_tag
            with open(VERSION_FILENAME, 'w',encoding='utf-8') as file:
                file.write('"""\n')
                file.write('Library Version.\n')
                file.write('"""\n')
                file.write(f'ATTACHMENT_DOWNLOADER_VERSION = "{version}"\n')
            return version

    @staticmethod
    def get(retry=True):
        """
        Get version number.
        """
        try:
            # pylint: disable=C0415
            from attachment_downloader.version import ATTACHMENT_DOWNLOADER_VERSION
            return ATTACHMENT_DOWNLOADER_VERSION
        except ModuleNotFoundError:
            if retry:
                Version.generate()
                return Version.get(False)
            return 'unknown'
        except ImportError:
            if retry:
                Version.generate()
                return Version.get(False)
            return 'unknown'

    @staticmethod
    def get_env_info():
        """
        Get environment information.
        """
        os_info = f"Release: {platform.release()}, Platform: {platform.platform()}"
        return f"(Python: {platform.python_version()}), OS: ({os_info}). Default Encoding: {sys.getdefaultencoding()}"
