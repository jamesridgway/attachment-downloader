from setuptools import setup

try:
    from pypandoc import convert
    read_md = lambda f: convert(f, 'rst')
except ImportError:
    print("warning: pypandoc module not found, could not convert Markdown to RST")
    read_md = lambda f: open(f, 'r').read()


setup(
    name='attachment-downloader',
    version='1.0.1',
    description='Simple tool for downloading email attachments for all emails in a given folder using an IMAP client.',
    long_description=read_md('README.md'),
    author='James Ridgway',
    url='https://github.com/jamesridgway/attachment-downloader',
    license='MIT',
    packages=['attachment_downloader'],
    scripts=['bin/attachment-downloader']
)
