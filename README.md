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

[python]: https://www.python.org
[postgresql]: https://www.postgresql.or
[redis]: https://redis.io
[node.js]: https://nodejs.org
[yarn]: https://yarnpkg.com
[npm]: https://npmjs.com

Optional, but useful:

- [ClamAV] for virus scanning uploads
- [InfluxDB] for metrics (see [`docs/managing.md`](docs/managing.md) for more
  details).
- A [Mailgun] API key for sending emails
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
git clone --recursive https://gitlab.com/elixire/elixire.git && cd elixire
```

Create some necessary directories:

```bash
mkdir -p images dumps thumbnails
```

Install [Python] dependencies using pip:

```bash
# You can use a virtual environment, too.
python3.6 -m pip install -Ur requirements.txt
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

Setup the directory structure in `./images`:

```bash
# Make sure you are running this from the repository root.
./utils/upgrade/folder_sharding.py
```

Configure the admin panel and frontend:

```bash
$EDITOR frontend/config.json
$EDITOR admin-panel/config.json
```

More information on configuring can be found in the `README.md` file of each
project:

- [frontend readme](https://gitlab.com/elixire/frontend#readme)
- [admin-panel readme](https://gitlab.com/elixire/admin-panel#readme)

Build the frontend and admin panel (this requires [Yarn]):

```bash
make
```

Configure elixire itself using [`config.py.example`](./config.py.example) as a
base:

```bash
cp config.py.example config.py

# Configure elixire to your liking.
$EDITOR config.py
```

Run the app:

```bash
python3.6 run.py
```

## Operator's Manual

The operator's manual is still under construction, but here's some important
notes:

- If you're running elixire behind a reverse proxy (which you should be), make
  sure to enable host forwarding:

```conf
location / {
    proxy_set_header Host $host;
    proxy_pass ...;
}
```

- If you get an error saying something like "route already registered", then you
  forgot to build the frontend. You can disable it in `config.py` or build it.
- Ensure that you redirect www to non-www or non-www to www or else the domain
  checking stuff won't be super happy (you'll not be able to fetch stuff
  properly).

### Tools

See [`docs/managing.md`](docs/managing.md) for more information on managing your
elixire instance.

## API Documentation

[See this repo](https://gitlab.com/elixire/api-docs) for the API documentation.
Both the client and admin API are documented there.

## Setting and running a test environment

⚠ **NOTE: NEVER RUN TESTS IN YOUR PRODUCTION ENVIRONMENT.**

Install [tox] manually (the [Python] package, not the messenger).

[tox]: https://pypi.org/project/tox

Create the testing users:

```bash
./manage.py adduser h@h.co hi hihihihi
./manage.py adduser a@a.co admin adminadmin
./manage.py adduser n@n.co nousage nousagenousage
./manage.py adduser q@q.co quotareached quotareached
```

Then, enter the [PostgreSQL] shell, `psql`, and run these queries:

```bash
psql -U postgres -d elixire
```

```sql
UPDATE users
SET admin = true
WHERE username = 'admin';

INSERT INTO domain_owners (domain_id, user_id)
VALUES (0, (SELECT user_id FROM users WHERE username = 'admin'));
```

Then you can run the tests with [tox]:

```bash
tox
```
