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

get pythone!!!

```bash
python3.6 -m pip install -Ur requirements.txt
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

```bash
cd utils
./adduser.py hi hi

# TODO: instructions for admin test user

./adduser.py nousage nousage
./adduser.py quotareached quotareached

cd ..
```

Then,
```bash
tox
```
