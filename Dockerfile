FROM python:3.13-alpine

WORKDIR /usr/src/app

COPY requirements.txt .
RUN pip install --no-cache-dir --requirement requirements.txt

COPY . .

CMD [ "python", "main.py", "watch", "--config", "$CONFIG" ]
