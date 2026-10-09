#!/usr/bin/env bash
# Regenerates the S/MIME test fixtures in this directory using OpenSSL 3.x.
#
# The keys generated here are for testing only. OpenSSL is only needed to regenerate the fixtures, not to run the tests.
set -euo pipefail
cd "$(dirname "$0")"

TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

openssl req -x509 -newkey rsa:2048 -nodes -keyout rsa-key.pem -out rsa-cert.pem -subj "/CN=rsa@example.com" \
    -days 36500 2>/dev/null
openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:P-256 -nodes -keyout ec-key.pem -out ec-cert.pem \
    -subj "/CN=ec@example.com" -days 36500 2>/dev/null

printf 'Content-Type: multipart/mixed; boundary="b"\r\n\r\n--b\r\nContent-Type: text/plain\r\n\r\nhello\r\n--b\r\nContent-Type: application/pdf; name="invoice.pdf"\r\nContent-Disposition: attachment; filename="invoice.pdf"\r\nContent-Transfer-Encoding: base64\r\n\r\nSGVsbG8gUERG\r\n--b--\r\n' > "$TMP/inner.eml"

encrypt() {
    local name=$1; shift
    openssl cms -encrypt -in "$TMP/inner.eml" -from sender@example.com -to recipient@example.com \
        -subject "$name" "$@" > "$name.eml"
}

encrypt aes256-cbc-ber -stream -aes256 rsa-cert.pem
encrypt aes128-gcm -aes-128-gcm rsa-cert.pem
encrypt aes256-gcm -aes-256-gcm rsa-cert.pem
encrypt rsa-oaep-sha1 -aes256 -recip rsa-cert.pem -keyopt rsa_padding_mode:oaep
encrypt rsa-oaep-sha256 -aes256 -recip rsa-cert.pem -keyopt rsa_padding_mode:oaep -keyopt rsa_oaep_md:sha256 \
    -keyopt rsa_mgf1_md:sha256
encrypt rsa-key-identifier -aes256 -keyid rsa-cert.pem
encrypt ec-sha1kdf -aes256 ec-cert.pem
encrypt ec-sha256kdf-gcm -aes-256-gcm -recip ec-cert.pem -keyopt ecdh_kdf_md:sha256
