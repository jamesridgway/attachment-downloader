FROM python:3.13-alpine AS build

RUN apk add --no-cache git
RUN pip install --no-cache-dir build

WORKDIR /src
COPY . .
RUN python -m build --wheel --outdir /dist


FROM python:3.13-alpine

LABEL org.opencontainers.image.title="attachment-downloader" \
      org.opencontainers.image.description="Download email attachments from an IMAP mailbox" \
      org.opencontainers.image.source="https://github.com/jamesridgway/attachment-downloader" \
      org.opencontainers.image.licenses="MIT"

COPY --from=build /dist/*.whl /tmp/
RUN pip install --no-cache-dir /tmp/*.whl && rm /tmp/*.whl

RUN adduser -D -u 1000 attachment-downloader && mkdir /downloads && chown attachment-downloader /downloads
USER attachment-downloader
WORKDIR /downloads
ENV AD_DOWNLOAD_FOLDER=/downloads

ENTRYPOINT ["attachment-downloader"]
