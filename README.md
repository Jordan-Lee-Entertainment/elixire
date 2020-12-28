# elixire

> "elixirae is the futureae"
>
> — lunae bunae genserv, 2018

elixire is an open source image host and link shortener written in [Python].

## Installation

### Requirements

- [Python] 3.7+
- [PostgreSQL]
- [Redis]
- [Node.js] LTS
  - [Yarn] and [npm]
- libmagic

[python]: https://www.python.org
[postgresql]: https://www.postgresql.org
[redis]: https://redis.io
[node.js]: https://nodejs.org
[yarn]: https://yarnpkg.com
[npm]: https://npmjs.com

Optional, but useful:

- [ClamAV] for virus scanning uploads
- [InfluxDB] for metrics (see [`docs/managing.md`](docs/managing.md) for more
  details).
- A SMTP server for outgoing email. We use [Mailgun], but any
  SMTP server should work.
- [Discord] webhooks for admin notifications

[clamav]: https://www.clamav.net
[influxdb]: https://www.influxdata.com
[mailgun]: https://mailgun.com
[discord]: https://discordapp.com

Make sure you have everything you want installed before proceeding.

### Installing

Clone the [git] repository:

[git]: https://git-scm.com

```bash
git clone https://gitlab.com/elixire/elixire.git && cd elixire
```

Create some necessary directories:

```bash
mkdir -p images dumps thumbnails
```

Install [Python] dependencies using any of:

#### bare virtualenvs

If you are using pip 20.3+, using the constraints file is mandatory for a
good experience.

```bash
python3 -m venv env
env/bin/pip install -U pip wheel
env/bin/pip install -U --editable . -c constraints.txt
```

#### virtualfish

```bash
vf new -p python3 elixire
vf activate elixire
pip install -U --editable . -c constraints.txt
```

Create the [PostgreSQL] database if it doesn't already exist:

```bash
createdb elixire
```

Execute the schema using `psql`:

```bash
# You want to edit schema.sql before continuing, specifically the "INSERT INTO
# domains" line, unless your main domain is "elixi.re".
$EDITOR schema.sql

# Your username might be different.
psql -U postgres -d elixire -f schema.sql
```

Configure elixire itself using [`config.example.py`](./config.example.py) as a
base:

```bash
cp config.example.py config.py

# Configure elixire to your liking.
$EDITOR config.py
```

Setup the directory structure in `./images`:

```bash
env/bin/python ./utils/upgrade/folder_sharding.py
```

(If you aren't using a virtualenv, replace `env/bin/python` with `python3` or
whatever your Python binary is.)

Run the app:

```bash
# bind to any wanted address
hypercorn --access-log - run:app --bind 0.0.0.0:8081

# when running in production, set the PYTHON_ENV variable to prod
env PYTHON_ENV=production hypercorn --access-log - run:app --bind 0.0.0.0:8081
```

## Post-installation

### Installing frontends

When putting elixi.re in production, you should host it behind a reverse proxy.
A reverse proxy is required if you wish to host any web-based frontends.

The available frontends are:

- [antichrist] which provides the main frontend for users.
- [admin-panel] to provide administration interfaces for the instance.

[antichrist]: https://gitlab.com/elixire/antichrist
[admin-panel]: https://gitlab.com/elixire/admin-panel

### Enabling host forwarding

When using a reverse proxy, it should be configured so that the `Host` header
is forwarded to elixire.

```conf
location / {
    proxy_set_header Host $host;
    proxy_pass ...;
}
```

#### Note on reverse proxying

(todo: elaborate on this?)

- Ensure that you redirect www to non-www or non-www to www or else the domain
  checking stuff won't be super happy (you'll not be able to fetch stuff
  properly).

### Creating the first user

Elixire instances do not come with any users (other than a specific user that
nobody can access), you will need to create your own user:

```
env/bin/python ./manage.py adduser <email> <username> <password>
```

And then edit that user so that it is admin on the database. Open a `psql` shell,
then type:

```
UPDATE users SET admin = true WHERE username = '<username>';
```

### Tools

See [`docs/managing.md`](docs/managing.md) for more information on managing your
elixire instance.

## API Documentation

[See this repo](https://gitlab.com/elixire/api-docs) for the API documentation.
Both the client and admin API are documented there.

## Setting and running a test environment

Install [tox] manually (the [Python] package, not the messenger).

[tox]: https://pypi.org/project/tox

Then you can run the tests with [tox]:

```bash
tox
```
