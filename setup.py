import os

from setuptools import setup, find_packages

from attachment_downloader.version_info import Version

Version.generate()

with open(os.path.abspath(os.path.join(os.path.dirname(__file__), 'requirements.txt'))) as f:
    install_reqs = f.read().splitlines()

setup(
    name='attachment-downloader',
    version=Version.get(),
    description='Simple tool for downloading email attachments for all emails in a given folder using an IMAP client.',
    long_description=open('README.rst').read(),
    author='James Ridgway',
    url='https://github.com/jamesridgway/attachment-downloader',
    license='MIT',
    packages=find_packages(),
    scripts=['bin/attachment-downloader'],
    install_requires=install_reqs
)
