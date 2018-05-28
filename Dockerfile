FROM ubuntu:xenial
MAINTAINER Ave Ozkal (dockere@ave.zone)

WORKDIR /elixire
ADD . /elixire

RUN apt-get update
RUN apt-get install -y python3 python3-pip git wget redis-server software-properties-common
RUN add-apt-repository 'deb http://apt.postgresql.org/pub/repos/apt/ xenial-pgdg main' -y
RUN wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | apt-key add -
RUN apt-get update
RUN apt-get install -y postgresql-10
RUN pip3 install -Ur requirements.txt

ENV NAME elixire
