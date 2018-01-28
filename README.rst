Attachment Downloader
=====================

Simple tool for downloading email attachments for all emails in a given
folder using an IMAP client.

Install:

::

    $ pip install attachment-downloader

Usage:

::

    Usage: attachment-downloader [options]

    Options:
      -h, --help            show this help message and exit
      --host=HOST           IMAP Host
      --username=USERNAME   IMAP Username
      --password=PASSWORD   IMAP Password
      --imap-folder=IMAP_FOLDER
                            IMAP Folder to extract attachments from
      --filename-template=FILENAME_TEMPLATE
                            Attachment filename (jinja2) template.
      --output=DOWNLOAD_FOLDER
                            Output directory for attachment download


Example:

::

    $ attachment-downloader --host imap.example.com --username mail@example.com --password pa55word \\
        --imap-folder invoices --output ~/Downloads

For full instructions and documentation visit: https://github.com/jamesridgway/attachment-downloader