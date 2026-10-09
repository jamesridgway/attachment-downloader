import os
import subprocess

from setuptools import setup, find_packages

ROOT = os.path.abspath(os.path.dirname(__file__))


def read(filename):
    with open(os.path.join(ROOT, filename), encoding='utf-8') as file:
        return file.read()


def version():
    if os.path.exists(os.path.join(ROOT, 'PKG-INFO')):
        return next(line.split(':', 1)[1].strip() for line in read('PKG-INFO').splitlines()
                    if line.startswith('Version:'))
    tag = subprocess.run(['git', 'describe', '--always', '--tags'], cwd=ROOT, capture_output=True, text=True,
                         check=True).stdout.strip()
    return tag.split('-g', maxsplit=1)[0].replace('-', '.') if '-g' in tag else tag


setup(
    name='attachment-downloader',
    version=version(),
    description='Simple tool for downloading email attachments for all emails in a given folder using an IMAP client.',
    long_description=read('README.md'),
    long_description_content_type='text/markdown',
    author='James Ridgway',
    url='https://github.com/jamesridgway/attachment-downloader',
    license='MIT',
    packages=find_packages(exclude=['tests', 'tests.*']),
    python_requires='>=3.10',
    scripts=['bin/attachment-downloader'],
    install_requires=read('requirements.txt').splitlines()
)
