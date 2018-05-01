elixi.re v2
===========

```
"elixirae is the futureae"
  - lunae bunae genserv, 2018
```

elixi.re is a imagehost solution, the v1 was written in PHP,
v2 is being written in Python.

*(no, we won't write Elixir)*

# Running

```bash
python3.6 -m pip install -Ur requirements.txt

# this sets up the folder structure in ./images for you
# NOTE: this script has ./images hardcoded.
./utils/upgrade/folder_sharding.py

python3.6 run.py
```

# Operator's Manual

**TODO**

Here's some important notes while this is still a todo:

- If you're proxying the instance (you should), enable host forwarding [like this](https://s.ave.zone/fjt.png).
- If you get an error saying something like "route already registered", then you forgot to build the frontend, either disable it or cd to `frontend`, run `npm install` and then `npm run build:production`. You need a reasonably decent node version.
- Ensure that you redirect www to non-www or non-www to www or else the domain checking stuff won't be super happy (you'll not be able to fetch stuff properly).

## Tools

 - `utils/adduser.py` adds a new user.
 - `utils/deletefile.py` deletes a file.
 - `utils/stats.py` displays neat facts about your instance.

# API Documentation

[See this repo](https://gitlab.com/elixire/api-docs) for API Docs.

# Running tests

**NOTE: DO NOT RUN TESTS IN YOUR PRODUCTION ENVIROMENT. AT ALL.**

Install `tox`, the python package.

```bash
cd utils

./adduser.py hi hi
./adduser.py admin admin
./adduser.py nousage nousage
./adduser.py quotareached quotareached

cd ..
```

After creating admin user, enter the PSQL Shell:
```sql
UPDATE users
SET admin = true
WHERE username = 'admin';
```

Then, run the tests with tox.
```bash
tox
```
