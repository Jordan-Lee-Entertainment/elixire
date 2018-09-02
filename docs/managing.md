# Managing your elixi.re instance

## Tools

### Administration

If you have built the [elixi.re admin panel (EAD)][ead], go to `/admin` to
manage your elixi.re instance.

[ead]: https://gitlab.com/elixire/admin-panel

### `manage.py`

`./manage.py` is a management script that supersedes most of the scripts in the
`utils/` directory. Use `./manage.py help` and `./manage.py help <operation>`
for help.

Keep in mind that `./manage.py` doesn't use the admin API -- it modifies the
database in-bulk and can be useful for certain operations.

### `utils/`

#### `utils/stats.py`

This script runs through your database to process information about your
elixi.re instance. Since we are GDPR compliant, we show two types of statistics:
public and private. You should not disclose any private statistics to anyone
other than your development team, as doing so is a violation of the GDPR.
Private statistics exist to determine the quality of service (e.g too many
files, image folder getting big, etc).

#### `utils/resetpasswd.py`

This script can be used to reset a single user's password manually.

### `utils/upgrade/`

Scripts in this directory are used to update the internal directory structure of
old elixi.re instances. These are needed when bringing an old instance up to
date.

Only run these scripts if necessary.

#### `utils/upgrade/folder_sharding.py`

This script is used to shard the `images/` directory. Previously, elixi.re kept
all images in a single directory. This script shards all images by the first
character of their filename for easier navigation.

#### `utils/upgrade/storage_filehash.py`

This script renames files in the `images/` directory to their respective hashes.

## d1

[d1] is elixi.re's domain checker. Its job is to check domains to make sure they
are pointing to the correct elixi.re instance. More information can be found on
the project page. It is recommended for production enviroments with lots of
domains. Make sure to set `SECRET_KEY` on your config if you want to use d1.

[d1]: https://gitlab.com/elixire/d1

## Metrics

elixi.re can send metric information to InfluxDB. From there, Grafana can show
you the data using pretty graphs so you can visualize instance information
better.
