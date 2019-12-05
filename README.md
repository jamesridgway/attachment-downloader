# Attachment Downloader
[![Build Status](https://travis-ci.org/jamesridgway/attachment-downloader.svg?branch=master)](https://travis-ci.org/jamesridgway/attachment-downloader)

Simple tool for downloading email attachments for all emails in a given folder using an IMAP client.

Install:

    $ pip install attachment-downloader

Usage:

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
      --delete              Delete downloaed E-Mails from Mailbox
      --delete-copy-folder=DELETE_COPY_FOLDER
                            IMAP folder to copy emails to before deleting them
Example:

    $ attachment-downloader --host imap.example.com --username mail@example.com --password pa55word \\
        --imap-folder invoices --output ~/Downloads

## Requirements
This tool requires Python 3+

This is not compatible with Python 2.

## Filename Template
By default attachments will be downloaded using their original filename to the folder specified by `-output`.

You can customise the download filename using a jinja2 template for the argument `--filename-template`.

The following variables are supported:
* `message_id`
* `attachment_name`
* `attachment_idx`
* `subject`
* `local_date`

In the following example, downloads will be placed within the output folder grouped into a folder hierarchy of date, message ID, subject:

    --filename-template="{{local_date}}/{{ message_id }}/{{ subject }}/{{ attachment_name }}"
