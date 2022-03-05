import os

VERSION_FILENAME = os.path.abspath(os.path.join(os.path.dirname(__file__), 'version.py'))
import subprocess


class Version:
    @staticmethod
    def generate():
        process = subprocess.Popen(["git", "describe", "--always", "--tags"], stdout=subprocess.PIPE, stderr=None)
        last_tag = process.communicate()[0].decode('ascii').strip()
        version = last_tag.split('-g')[0].replace('-', '.') if '-g' in last_tag else last_tag
        with open(VERSION_FILENAME, 'w') as f:
            f.write(f'ATTACHMENT_DOWNLOADER_VERSION = "{version}"\n')
        return version

    @staticmethod
    def get(retry=True):
        try:
            from attachment_downloader.version import ATTACHMENT_DOWNLOADER_VERSION
            return ATTACHMENT_DOWNLOADER_VERSION
        except ModuleNotFoundError as e:
            if retry:
                Version.generate()
                return Version.get(False)
            return 'unknown'
        except ImportError as e:
            if retry:
                Version.generate()
                return Version.get(False)
            return 'unknown'
