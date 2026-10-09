# Attachment Downloader
[![CI](https://github.com/jamesridgway/attachment-downloader/actions/workflows/ci.yml/badge.svg)](https://github.com/jamesridgway/attachment-downloader/actions/workflows/ci.yml)

Simple tool for downloading email attachments for all emails in a given folder using an IMAP client.

## Install

    $ pip install attachment-downloader

Attachment Downloader requires Python 3.10 or later, and runs on Linux, macOS and Windows.

## Usage

    $ attachment-downloader --host imap.example.com --username mail@example.com --password pa55word \
        --imap-folder invoices --output ~/Downloads

If `--password` is not given, the password is prompted for, or read from standard input when it is not a terminal.

    Usage: attachment-downloader [options]

    Options:
      -h, --help            show this help message and exit
      --host=HOST           IMAP Host
      --username=USERNAME   IMAP Username
      --password=PASSWORD   IMAP Password
      --imap-folder=IMAP_FOLDER
                            IMAP Folder to extract attachments from
      --filename-regex=FILENAME_REGEX
                            Regex that the attachment filename must match against
      --sent-to-regex=SENT_TO_REGEX
                            Regex that the sent_to must match against
      --subject-regex=SUBJECT_REGEX
                            Regex that the subject must match against
      --subject-regex-ignore-case
                            Provide this option to ignore regex case in subject.
      --subject-regex-match-anywhere
                            Provide this option to search anywhere in subject
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
      --port=PORT           Specify imap server port (defaults to 993 for TLS and
                            143 otherwise
      --unsecure            disable encrypted connection (not recommended)
      --starttls            enable STARTTLS (not recommended)
      --smime-key=SMIME_KEY
                            Private key used to decrypt S/MIME encrypted emails
                            (PEM, or a PKCS#12 .p12/.pfx bundle)
      --smime-cert=SMIME_CERT
                            Certificate (PEM) used to decrypt S/MIME encrypted
                            emails (optional for PKCS#12 bundles)
      --smime-key-password=SMIME_KEY_PASSWORD
                            Password for the S/MIME private key or PKCS#12 bundle
      --log-level=LOGLEVEL  Set the log level to DEBUG, INFO, WARNING, ERROR, or
                            CRITICAL (default is INFO)

## Selecting Messages

### Folders
Messages are read from the folder given by `--imap-folder`. If you wish to search through all messages regardless of
folder, omit the `--imap-folder` argument.

### Subject
`--subject-regex` selects messages whose subject starts with a match for the regex. Add
`--subject-regex-match-anywhere` to match anywhere in the subject, and `--subject-regex-ignore-case` to ignore case.

### Recipient
`--sent-to-regex` selects messages where any recipient's email address contains a match for the regex.

### Attachment Filename
`--filename-regex` only downloads attachments whose filename contains a match for the regex.

### Date
Date filtering can be performed by specifying one or both of the date arguments:

    --date-after="2021-02-06T13:00:00" --date-before="2021-02-06T13:25:00"

Dates should be provided in ISO format, e.g: `2021-02-06T13:25:00` or `2021-02-06T13:25:00+01:00`.

If a zone offset is not provided UTC will be assumed. This also applies to messages whose date has no zone offset.

## Filename Template
By default attachments will be downloaded using their original filename to the folder specified by `--output`.

You can customise the download filename using a jinja2 template for the argument `--filename-template`.

The following variables are supported:
* `message_id`
* `attachment_name`
* `attachment_idx`
* `subject`
* `date`
* `from_email`
* `folder`

In the following example, downloads will be placed within the output folder grouped into a folder hierarchy of date, message ID, subject:

    --filename-template="{{date}}/{{ message_id }}/{{ subject }}/{{ attachment_name }}"

The datetime of the message can also be formatted in the output filename, for example:

    --filename-template "{{date.strftime('%Y-%m-%d')}} {{ attachment_name }}"

The template is checked before connecting to the mailbox, so a mistake is reported straight away.

## Deleting Messages
`--delete` deletes each message once its attachments have been downloaded. A message is only deleted when at least one
attachment was downloaded and none failed, so messages without matching attachments are kept.

Add `--delete-copy-folder` to copy each message to another folder before it is deleted.

## S/MIME

### Encrypted Emails
Attachments can be extracted from S/MIME encrypted emails by providing the recipient's private key and certificate.

Using a PEM private key and certificate:

    --smime-key=private-key.pem --smime-cert=certificate.pem

Using a PKCS#12 bundle (as exported from most mail clients), which contains both the key and certificate:

    --smime-key=credentials.p12 --smime-key-password=pa55word

Encrypted emails which cannot be decrypted with the given credentials are logged and skipped. Unencrypted emails are
processed as normal.

The following algorithms are supported:

| Purpose            | Algorithms                                                              |
| ------------------ | ----------------------------------------------------------------------- |
| Content encryption | AES-CBC and AES-GCM (128, 192 and 256 bit)                              |
| RSA keys           | RSAES-PKCS1-v1_5 and RSAES-OAEP                                         |
| EC keys            | ECDH (NIST curves) with the X9.63 KDF (SHA-1 or SHA-2) and AES key wrap |

S/MIME support is implemented in Python on top of the `cryptography` package, so no additional tools (such as
OpenSSL) need to be installed.

### Signed Emails
Attachments are extracted from S/MIME signed emails automatically, including emails with an opaque signature
(`application/pkcs7-mime; smime-type=signed-data`) and emails which are both signed and encrypted. No options are
required for signed emails.

Signatures are not verified. Use your mail client if you need to confirm who signed an email.

## Environment Variables
Every option can also be set with an environment variable. Options given on the command line take precedence.

| Option                           | Environment variable              |
| -------------------------------- | --------------------------------- |
| `--host`                         | `AD_HOST`                         |
| `--username`                     | `AD_USERNAME`                     |
| `--password`                     | `AD_PASSWORD`                     |
| `--imap-folder`                  | `AD_IMAP_FOLDER`                  |
| `--filename-regex`               | `AD_FILENAME_REGEX`               |
| `--sent-to-regex`                | `AD_SENT_TO_REGEX`                |
| `--subject-regex`                | `AD_SUBJECT_REGEX`                |
| `--subject-regex-ignore-case`    | `AD_SUBJECT_REGEX_IGNORE_CASE`    |
| `--subject-regex-match-anywhere` | `AD_SUBJECT_REGEX_MATCH_ANYWHERE` |
| `--date-after`                   | `AD_DATE_AFTER`                   |
| `--date-before`                  | `AD_DATE_BEFORE`                  |
| `--filename-template`            | `AD_FILENAME_TEMPLATE`            |
| `--output`                       | `AD_DOWNLOAD_FOLDER`              |
| `--delete`                       | `AD_DELETE`                       |
| `--delete-copy-folder`           | `AD_DELETE_COPY_FOLDER`           |
| `--port`                         | `AD_PORT`                         |
| `--unsecure`                     | `AD_UNSECURE`                     |
| `--starttls`                     | `AD_STARTTLS`                     |
| `--smime-key`                    | `AD_SMIME_KEY`                    |
| `--smime-cert`                   | `AD_SMIME_CERT`                   |
| `--smime-key-password`           | `AD_SMIME_KEY_PASSWORD`           |
| `--log-level`                    | `AD_LOGLEVEL`                     |

Flags such as `AD_DELETE` are enabled by `1`, `true`, `yes` or `on`, and disabled by any other value.

### Running Repeatedly
Set `AD_INTERVAL` to a number of seconds to keep running, checking the mailbox again after each interval.

## Docker
A Dockerfile is included, which is configured using the environment variables above:

    $ docker build -t attachment-downloader .
    $ docker run --rm -v ~/Downloads:/downloads \
        -e AD_HOST=imap.example.com -e AD_USERNAME=mail@example.com -e AD_PASSWORD=pa55word \
        -e AD_IMAP_FOLDER=invoices -e AD_DOWNLOAD_FOLDER=/downloads -e AD_INTERVAL=3600 \
        attachment-downloader

## Release Notes
See [GitHub Releases](https://github.com/jamesridgway/attachment-downloader/releases).

## Reporting Issues and Contributing
If you spot any issues or have a feature request please feel free to raise an issue, or even better, propose a pull request.

## Development
Create a virtual environment with the development dependencies, then run the tests and linter:

    $ ./setup.sh
    $ ./run-tests.sh
    $ ./run-pylint.sh

### Test Mail Server
For local testing of the tool, a docker-compose stack is included which provides a Postfix, Dovecot, PostfixAdmin and Roundcube setup.

Docker compose can be run using

    docker-compose up

The login for [PostfixAdmin](http://localhost/postfixadmin) is `root` / `L3tm31n`

The following mailboxes will also be created which can be accessed via [roundcube](http://localhost/roundcubemail):

| Mailbox             | Password |
| ------------------- | -------- |
| `user1@example.com` | `Pass11` |
| `user2@example.com` | `Pass22` |
