Elixire v2
==========

```
"elixirae is the futureae"
  - lunae bunae genserv, 2018
```

Elixire is an image host solution; v1 was written in PHP,
v2 is being written in Python.

*(no, we won't write Elixir, read BACKEND.md for the reason)*

# Installation and Running

**Dockerfiles exist in this repository. Do not attempt to run them.
(Merge Requests "fixing" them will be closed.)**

Requirements:
 - Python 3.6+
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
python3.6 -m pip install -Ur requirements.txt

# make sure those folders exist
mkdir images
mkdir dumps
mkdir thumbnails

# Please edit schema.sql before continuing.
# Specially the "INSERT INTO domains" line.
psql -U postgres -f schema.sql

# Edit frontend/config.json and admin-panel/config.json
# so they're pointing to your domain.

# This sets up the folder structure in ./images for you.
# Do not run 'cd utils/upgrade' then run the script.
./utils/upgrade/folder_sharding.py

# Update frontend and admin-panel repositories.
# Use this makefile task to update your instance.
make update

# Build the frontend and the admin-panel.
make 

# Read carefully over the configuration file
# to enable/disable instance features (like registration and webhooks).
cp config.py.example config.py

# Run application, also works under external process managers.
python3.6 run.py
```

# Operator's Manual

**TODO**

Here's some important notes while this is still a todo:

- If you're proxying the instance (you should), enable host forwarding [like this](https://old-s.ave.zone/fjt.png).
- If you get an error saying something like "route already registered", then you forgot to build the frontend, either disable it or build the frontend. **You need a reasonably decent node version.**
- Ensure that you redirect www to non-www or non-www to www or else the domain checking stuff won't be super happy (you'll not be able to fetch stuff properly).

## Tools

Please look under the `docs/` directory for more complete tooling documentation.

# API Documentation

[See this repo](https://gitlab.com/elixire/api-docs) for API Docs.
Both the Client API and the Admin API are documented there.

# Running tests

**NOTE: DO NOT RUN TESTS IN YOUR PRODUCTION ENVIRONMENT. AT ALL.**

Install `tox` manually (the python package, not the messenger).

```bash
cd utils

./adduser.py h@h.co hi hihihihi
./adduser.py a@a.co admin adminadmin
./adduser.py n@n.co nousage nousagenousage
./adduser.py q@q.co quotareached quotareached

cd ..
```

After creating admin user, enter the PSQL Shell:
```sql
UPDATE users
SET admin = true
WHERE username = 'admin';
```

Make sure to insert some big ratelimits to be able to run
the test battery, 1000/1s should be enough for both user ratelimits
and IP based ratelimits.

Then, run the tests with tox.
```bash
tox
```
