FROM debian:buster-slim

RUN apt update && apt -y upgrade

RUN apt -y install python3 python3-pip

RUN mkdir /build
WORKDIR /build
COPY requirements.txt .

RUN pip3 install -r requirements.txt

RUN rm -rf /build

RUN mkdir /app
WORKDIR /app
COPY project/ /app/
