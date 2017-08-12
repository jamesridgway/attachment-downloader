from setuptools import setup

setup(
    name='attachment-downloader',
    version='1.0.0',
    description='Downloads mail attachment',
    author='James Ridgway',
    url='https://github.com/jamesridgway/attachment-downloader',
    license='MIT',
    entry_points={
        'console_scripts': [
            'attachment-downloader = attachment_downloader',
        ]
    }
)
