# Elixire

```
"elixirae is the futureae"
  - lunae bunae genserv, 2018
```

Elixire is an open source image host solution.

The first iteration of Elixire was written in PHP,
then rewritten in Python and this is the main language
we are working on.

_(no, we won't write Elixir, read BACKEND.md for the reason)_

# Installation and Running

**Dockerfiles exist in this repository. Do not attempt to run them.
(Merge Requests "fixing" them will be closed.)**

Requirements:

- Python 3.7+ (3.8 recommended)
- PostgreSQL
- Redis
- A decent version of Node

Optional requirements:

- ClamAV, for virus scanning of uploads.
- InfluxDB, for metrics (look into `docs/MANAGE.md` for more detail).
- Mailgun, so that the instance becomes able to send emails to users.
- Discord webhooks (so that the admins know when a malicious
  file was uploaded, etc).

```bash
git clone https://gitlab.com/elixire/elixire.git
cd elixire

# Download the current versions for frontend and admin-panel.
git submodule init
git submodule update

# You are able to use a virtual enviroment if you want.
python3.7 -m pip install -Ur requirements.txt

# Please edit schema.sql before continuing.
# Specially the "INSERT INTO domains" line.
psql -U postgres -f schema.sql

# Read carefully over the configuration file
# to enable/disable instance features (like registration and webhooks).
cp config.py.example config.py

# Edit frontend/config.json and admin-panel/config.json
# so they're pointing to your domain.

# Update frontend and admin-panel repositories.
# Use this makefile task to update your instance.
make update

# Build the frontend and the admin-panel.
make

# Run application, also works under external process managers.
hypercorn run.py --access-log - --bind 0.0.0.0:8081
```

# Operator's Manual

**TODO**

Here's some important notes while this is still a todo:

- If you're reverse proxying the instance (you should), enable Host header forwarding in your reverse proxy (such as `proxy_set_header Host $host;` in nginx).
- If you get an error saying something like "route already registered", then you forgot to build the frontend, either disable it or build the frontend. **You need a reasonably decent node version.**
- Ensure that you redirect www to non-www or non-www to www or else the domain checking stuff won't be super happy (you'll not be able to fetch stuff properly).

## Tools

Please look under the `docs/` directory for more complete tooling documentation.

# API Documentation

[See this repo](https://gitlab.com/elixire/api-docs) for API Docs.
Both the Client API and the Admin API are documented there.

# Setting and running a test environment

**NOTE: It is not recommended to run the test suite in production environments,
as it will run against the currently configured database.**

Install `tox` globally, as that will take care of creating a dedicated
virtual environment for testing:

```
python3 -m pip install tox
```

Then, run it.

```bash
tox
```
