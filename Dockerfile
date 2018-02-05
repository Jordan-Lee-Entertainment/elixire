FROM python:latest

WORKDIR /elixire
ADD . /elixire

RUN pip3 install -Ur requirements.txt

ENV NAME elixire

CMD ["python3", "run.py"]
