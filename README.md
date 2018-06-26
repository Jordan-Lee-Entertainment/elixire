Elixire v2
==========

```
"elixirae is the futureae"
  - lunae bunae genserv, 2018
```

Elixire is an image host solution, the v1 was written in PHP,
v2 is being written in Python.

*(no, we won't write Elixir, read BACKEND.md for the reason)*

# Running

**Dockerfiles exist in this repository. Do not attempt to run them.
(Merge Requests "fixing" them will be closed.)**

Requirements:
 - Python 3.6+
 - PostgreSQL
 - Redis
 - A decent version of Node.

Optional requirements:
 - ClamAV

```bash
git clone https://gitlab.com/elixire/elixire.git
cd elixire

# download the current versions for frontend and admin-panel
git submodule init
git submodule update

# you can use a virtual enviroment if you want.
python3.6 -m pip install -Ur requirements.txt

mkdir images
mkdir dumps
mkdir thumbnails

# Please edit schema.sql before continuing.
# Specially the "INSERT INTO domains" line.
psql -U postgres -f schema.sql

# this sets up the folder structure in ./images for you
# do not run 'cd utils/upgrade' then run the script.
./utils/upgrade/folder_sharding.py

# Update frontend and admin-panel repositories
make update

# Build the frontend and the admin-panel
make 

# Read carefully over the configuration file
# as 

# run application, can be under pm2 or something.
python3.6 run.py
```

# Operator's Manual

**TODO**

Here's some important notes while this is still a todo:

- If you're proxying the instance (you should), enable host forwarding [like this](https://old-s.ave.zone/fjt.png).
- If you get an error saying something like "route already registered", then you forgot to build the frontend, either disable it or build the frontend. **You need a reasonably decent node version.**
- Ensure that you redirect www to non-www or non-www to www or else the domain checking stuff won't be super happy (you'll not be able to fetch stuff properly).

## Tools

 - `utils/adduser.py` to add a new user into the instance.
 - `utils/stats.py` displays neat facts about your instance.
 - `utils/resetpasswd.py` in the case a user wants to reset a password.
 - `utils/renamefile.py` in the case you want to rename a file's shortname.

More utilities are under the `utils/` directory, Most of the utils are
superseeded by their equivalents in the Admin API.

# API Documentation

[See this repo](https://gitlab.com/elixire/api-docs) for API Docs.
Both the Client API and the Admin API are documented over there.

# Running tests

**NOTE: DO NOT RUN TESTS IN YOUR PRODUCTION ENVIRONMENT. AT ALL.**

Install `tox`, the python package.

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
