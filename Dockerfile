FROM python:3.13-alpine

WORKDIR /usr/src/app

RUN apk add --update --no-cache wget curl openssh rsync lftp

COPY requirements.txt .
RUN pip install --no-cache-dir --requirement requirements.txt

COPY . .

ENV CONFIG config.yaml
CMD exec python main.py watch --config $CONFIG
