FROM python:3.10-slim-buster

WORKDIR /usr/src/app

COPY requirements.txt requirements.txt

RUN pip install -r requirements.txt

COPY . /usr/src/app

ENV API_KEY=${IEXCLOUD_TOKEN}
RUN export API_KEY=${API_KEY}