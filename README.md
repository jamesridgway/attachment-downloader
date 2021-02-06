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
      --subject-regex=SUBJECT_REGEX
                            Regex that the subject must match against
      --date-after=DATE_AFTER
                            Select messages after this date
      --date-before=DATE_BEFORE
                            Select messages before this date
      --filename-template=FILENAME_TEMPLATE
                            Attachment filename (jinja2) template.
      --output=DOWNLOAD_FOLDER
                            Output directory for attachment download
      --delete              Delete downloaded emails from Mailbox
      --delete-copy-folder=DELETE_COPY_FOLDER
                            IMAP folder to copy emails to before deleting them

Example:

    $ attachment-downloader --host imap.example.com --username mail@example.com --password pa55word \\
        --imap-folder invoices --output ~/Downloads

### Messages from all folders
If you wish to search through all messages regardless of folder, omit the `--imap-folder` argument.

### Date Filtering
Date filtering can be performed by specifying one or both of the date arguments:

    --date-after="2021-02-06T13:00:00" --date-before="2021-02-06T13:25:00"

Dates should be provided in ISO format, e.g: `2021-02-06T13:25:00` or `2021-02-06T13:25:00`.

If a zone offset is not provided UTC will be assumed.

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
* `date`

In the following example, downloads will be placed within the output folder grouped into a folder hierarchy of date, message ID, subject:

    --filename-template="{{date}}/{{ message_id }}/{{ subject }}/{{ attachment_name }}"

The datetime of the message can also be formatted in the output filename, for example:

    --filename-template "{{date.strftime('%Y-%m-%d')}} {{ attachment_name }}"