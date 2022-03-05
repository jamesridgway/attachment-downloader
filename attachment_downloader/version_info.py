import os
import platform
import subprocess

VERSION_FILENAME = os.path.abspath(os.path.join(os.path.dirname(__file__), 'version.py'))


class Version:
    @staticmethod
    def generate():
        process = subprocess.Popen(["git", "describe", "--always", "--tags"], stdout=subprocess.PIPE, stderr=None)
        last_tag = process.communicate()[0].decode('ascii').strip()
        version = last_tag.split('-g', maxsplit=1)[0].replace('-', '.') if '-g' in last_tag else last_tag
        with open(VERSION_FILENAME, 'w') as file:
            file.write(f'ATTACHMENT_DOWNLOADER_VERSION = "{version}"\n')
        return version

    @staticmethod
    def get(retry=True):
        try:
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
        os_info = f"Release: {platform.release()}, Platform: {platform.platform()}"
        return f"(Python: {platform.python_version()}), OS: ({os_info})"
