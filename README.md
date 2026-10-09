# Attachment Downloader
[![CI](https://github.com/jamesridgway/attachment-downloader/actions/workflows/ci.yml/badge.svg)](https://github.com/jamesridgway/attachment-downloader/actions/workflows/ci.yml)

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
                            Regex that the subject must start with
      --subject-regex-ignore-case
                            Ignore case when matching subject
      --subject-regex-match-anywhere
                            Search entire subject for regex match
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

### S/MIME Encrypted Emails
Attachments can be extracted from S/MIME encrypted emails by providing the recipient's private key and certificate.

Using a PEM private key and certificate:

    --smime-key=private-key.pem --smime-cert=certificate.pem

Using a PKCS#12 bundle (as exported from most mail clients), which contains both the key and certificate:

    --smime-key=credentials.p12 --smime-key-password=pa55word

As with the other options, these can also be provided via the `AD_SMIME_KEY`, `AD_SMIME_CERT` and
`AD_SMIME_KEY_PASSWORD` environment variables.

Encrypted emails which cannot be decrypted with the given credentials are logged and skipped. Unencrypted emails are
processed as normal.

The following algorithms are supported:

| Purpose            | Algorithms                                                       |
| ------------------ | ---------------------------------------------------------------- |
| Content encryption | AES-CBC and AES-GCM (128, 192 and 256 bit)                       |
| RSA keys           | RSAES-PKCS1-v1_5 and RSAES-OAEP                                  |
| EC keys            | ECDH (NIST curves) with the X9.63 KDF (SHA-1 or SHA-2) and AES key wrap |

S/MIME support is implemented in Python on top of the `cryptography` package, so no additional tools (such as
OpenSSL) need to be installed.

### S/MIME Signed Emails
Attachments are extracted from S/MIME signed emails automatically, including emails with an opaque signature
(`application/pkcs7-mime; smime-type=signed-data`) and emails which are both signed and encrypted. No options are
required for signed emails.

Signatures are not verified. Use your mail client if you need to confirm who signed an email.

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
* `from_email`

In the following example, downloads will be placed within the output folder grouped into a folder hierarchy of date, message ID, subject:

    --filename-template="{{date}}/{{ message_id }}/{{ subject }}/{{ attachment_name }}"

The datetime of the message can also be formatted in the output filename, for example:

    --filename-template "{{date.strftime('%Y-%m-%d')}} {{ attachment_name }}"
    
## Reporting Issues and Contributing
If you spot any issues or have a feature request please feel free to raise an issue, or even better, propose a pull request.

## Testing
For local testing of the tool, a docker-compose stack is included which provides a Postfix, Dovecot, PostfixAdmin and Roundcube setup.

Docker compose can be run using

    docker-compose up

The login for [PostfixAdmin](http://localhost/postfixadmin) is `root` / `L3tm31n`

The following mailboxes will also be created which can be accessed via [roundcube](http://localhost/roundcubemail):

| Mailbox             | Password |
| ------------------- | -------- |
| `user1@example.com` | `Pass11` |
| `user2@example.com` | `Pass22` |
