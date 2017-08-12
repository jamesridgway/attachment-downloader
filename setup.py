from setuptools import setup

setup(
    name='attachment-downloader',
    version='1.0.2',
    description='Simple tool for downloading email attachments for all emails in a given folder using an IMAP client.',
    long_description=open('README.rst').read(),
    author='James Ridgway',
    url='https://github.com/jamesridgway/attachment-downloader',
    license='MIT',
    packages=['attachment_downloader'],
    scripts=['bin/attachment-downloader']
)
