FROM python:3-alpine

WORKDIR /usr/src/app

COPY . .

RUN apk add --no-cache git

RUN pip install --no-cache-dir .

CMD [ "attachment-downloader" ]
