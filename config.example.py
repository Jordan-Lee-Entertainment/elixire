# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

################################################################################
#
#          ___      _                               _____
#    ___  / (_)  __(_)_______     _________  ____  / __(_)___ _
#   / _ \/ / / |/_/ / ___/ _ \   / ___/ __ \/ __ \/ /_/ / __ `/
#  /  __/ / />  </ / /  /  __/  / /__/ /_/ / / / / __/ / /_/ /
#  \___/_/_/_/|_/_/_/   \___/   \___/\____/_/ /_/_/ /_/\__, /
#                                                     /____/
#
################################################################################
#
#  Please take the time to read through all of the available options.
#  There's a lot of them!
#
################################################################################

# HTTP server listening options.
#
# You'll probably want to setup a reverse-proxy instead of directly exposing
# it to the internet. (Something like Nginx, probably.)
HOST = "localhost"
PORT = 8080

# If the elixire instance is being served behind Cloudflare.
# This setting toggles how elixire fetches the request IP.
CLOUDFLARE = False

################################################################################

# The name of this elixire instance. This will appear in `/api/hello` and in
# any sent emails.
INSTANCE_NAME = "elixi.re"

# The primary URL that your instance will be accessible from. It's assumed that
# a frontend will be accessible here. This is also linked to in emails that try
# to direct the user to the website.
MAIN_URL = "https://elixi.re"

# The main invite to the Discord server of this instance. It's exposed in
# `/api/hello` and is sent to users via email upon registration.
MAIN_INVITE = "https://discord.gg/123456"

# The email that will be given to users for support. Used in emails.
SUPPORT_EMAIL = "support@elixi.re"

################################################################################

# SMTP credentials for sending emails. (Used during account creation, sending
# data dumps, etc.)
#
# NOTE: If this is set to `None`, then no emails will be sent at all. If you
#       want this, then make sure to disable account approvals, as those send
#       emails.
SMTP_CONFIG = {
    "from": "elixi.re <automated@somewhere>",
    "host": "smtp.mailgun.org",
    "port": 587,
    # "tls", "starttls", or None
    "tls_mode": "tls",
    "username": "postmaster@somewhere",
    "password": "something",
}

# Disabled features return HTTP 503 to any requests.
#
# Disabling certain features is useful for private instances or for disabling
# features when debugging during heavy load.

UPLOADS_ENABLED = True
SHORTENS_ENABLED = True
REGISTRATIONS_ENABLED = True

# Allow users to change their own profile information?
#
# e.g. changing username, email, password, default domain, default subdomain,
# password, etc.
PATCH_API_PROFILE_ENABLED = True

# Send emails when a user's account is activated?
NOTIFY_ACTIVATION_EMAILS = True

# Should accounts be manually activated or will they be activated by default?
REQUIRE_ACCOUNT_APPROVALS = True

# Acceptable MIME types for uploads.
#
# NOTE: Admins are able to bypass this check by specifying `?admin=1`.
# The default frontends does this automatically when an admin is logged in.
ACCEPTED_MIMES = [
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/webp",
    "image/svg+xml",
    "audio/webm",
    "video/webm",
]

# MIME types in this dict that, when detected as the file being uploaded,
# will have their extension forced to be the given one.
#
# By default, forces all image/jpeg files to have a jpg extension.
FORCE_EXTENSION = {"image/jpeg": ".jpg"}

# MIME types in this dict that, when detected as the file being uploaded,
# will also allow the given extension list as the file extension.
#
# By default, allows all application/octet-stream files to not
# have any extension.
INCLUDE_EXTENSIONS = {"application/octet-stream": [""]}


################################################################################

# Mailgun API credentials for sending emails.
# (Account deletion, data dump requests, etc.)
MAILGUN_DOMAIN = ""
MAILGUN_API_KEY = ""

# PostgreSQL database credentials.
db = {
    "host": "localhost",
    "user": "postgres",
    "password": "",
    # "database": "elixire"
}

# The address to the Redis instance.
# Example: `redis://localhost:6379/0"`
redis = "redis://localhost"

################################################################################

# Makes the API return URLs with `https://` instead of `http://`.
USE_HTTPS = True

# Makes the application server send the frontend and admin panel HTML files
# according to request URL. Both must be built (see `README.md`) for this to
# work properly.
#
# `/` is linked to `./frontend/output/index.html` and `/admin` is linked to
# `./admin-panel/build/index.html`.
ENABLE_FRONTEND = True

# The path to the images folder on disk.
# All uploaded images will be stored here.
#
# NB: The scripts in ./utils assume that your images are stored at the default
#     path ("./images"). Keep this in mind when changing this value.
IMAGE_FOLDER = "./images"

# Allow users to request data dumps?
#
# A data dump is a ZIP file containing all of the user's data.
# When a user requests a data dump, it's processed in the background and they
# are sent a link to it via email.
DUMP_ENABLED = True

# The path to the folder on disk to store data dumps in (temporarily).
DUMP_FOLDER = "./dumps"

# The amount of time to wait between old data dump checks in seconds.
#
# The dump janitor checks the dump folder for dumps that are over 6 hours old
# and deletes them to save space.
DUMP_JANITOR_PERIOD = 600

################################################################################

# The secret key to use for d1.
#
# d1 is a domain security checker for elixire instances. d1 verifies that all
# of the domains of your instance point to your own instance, and that they're
# up and running.
#
# You can generate a key with:
#  >>> from cryptography.fernet import Fernet
#  >>> Fernet.generate_key()
#
# Make sure to use the same key with d1. To disable d1 integration,
# set this to `None`.
SECRET_KEY = None

# The token shared secret. This is used in token generation in authentication.
#
# **DON'T LET ANYONE KNOW THIS SECRET!**
#
# To generate a valid key, spawn Python and then:
#  >>> from os import urandom
#  >>> urandom(48)
#  b"<some random results here>"
TOKEN_SECRET = b""

# How long are timed tokens valid for in seconds?
# Default value is 3 days.
TIMED_TOKEN_AGE = 259200

################################################################################

# Enable metrics collection?
#
# Metrics allows you to monitor various datapoints of your elixire instance with
# InfluxDB. Numbers such as the total number of users, file uploads, and the
# amount of files being uploaded hourly are available.
#
# aioinflux is used to send metric data to InfluxDB.
ENABLE_METRICS = False
METRICS_DATABASE = "elixire"

# InfluxDB credentials. These are irrelevant when `ENABLE_METRICS` is `False`.
INFLUX_HOST = ("localhost", 8086)
INFLUX_USER = "admin"
INFLUX_PASSWORD = "123"

# Should an authenticated InfluxDB connection be used?
INFLUXDB_AUTH = False

# Should HTTPS be used in the InfluxDB connection?
INFLUX_SSL = False

# ADVANCED: The limits of the metrics worker.
#
# Instead of sending a datapoint to InfluxDB every time there is one, we
# sent a maximum of `METRICS_LIMIT[0]` datapoints every `METRICS_LIMIT[1]`
# seconds in the background.
METRICS_LIMIT = (100, 3)

# The following settings configure the metrics compator.
# Do not change those unless you know what you're doing.
#
# For more information, see https://gitlab.com/elixire/elixire/issues/78.
# The metrics compactor compacts large amounts of datapoints so that InfluxDB
# doesn't choke on the data when loading historical data.

# The amount of time in seconds that the compactor will split datapoints into.
#
# It is set to 1 hour, so all things such as per-second `request` / `response`
# will become `request_hour` and `response_hour`.
METRICS_COMPACT_GENERALIZE = 3600

# METRICS_COMPACT_KEEP_POINTS sets the maximum
# amount of time pre-compacted datapoints
# can still lay around before getting cleaned.
#
# By default it is set to 10 days, but it can
# be changed if your grafana instance is starting to
# have problems with the amount of data
METRICS_COMPACT_KEEP_POINTS = 10 * 86400

################################################################################

# How long to ban users for. Users are temporarily banned from making requests
# due to ratelimit violations.
#
# For bans of authenticated requesters, `BAN_PERIOD` is used. `IP_BAN_PERIOD` is
# used for unauthenticated requests.
#
# Examples: "1 day", "6 hours", "10 seconds", etc.
BAN_PERIOD = "6 hours"
IP_BAN_PERIOD = "5 minutes"

# How many ratelimits can be triggered by a client before they get banned?
RL_THRESHOLD = 10

################################################################################

# Sets the minimum shortname length (for both image uploads and shortens).
SHORTNAME_LEN = 3

# The number of characters in a URL that the application is willing to shorten.
MAX_SHORTEN_URL_LEN = 250

# Run `clamdscan` on every upload?
#
# The multicore option will be used, so this isn't recommended on low-end
# machines.
UPLOAD_SCAN = False

# How long virus scans can take in seconds before they're moved to the
# background? (Can be an `int` or `float`.)
#
# See https://gitlab.com/elixire/elixire/issues/35 for more details.
#
# When the virus scan is taking too long and it exceeds this threshold, the link
# is given to the user and the scan continues in the background so that the user
# isn't stuck waiting for the upload to finish. Should a malicious file be
# found, the file is deleted as normal.
SCAN_WAIT_THRESHOLD = 1

# Should we strip EXIF metadata for JPEGs?
#
# This features requires the Pillow library (it should be already installed by
# default).
CLEAR_EXIF = False

# The growth ratio to prevent EXIF stripping at.
#
# To prevent potential exploits of the EXIF stripping feature, we compare the
# size of images before and after the EXIF data has been stripped.
# If `exif_cleaned_filesize / regular_filesize` is bigger than this number, we
# just use the image before the EXIF data was stripped.
#
# Using anything below 1.25 might cause false positives.
EXIF_INCREASELIMIT = 2

# The size decrease factor for duplicated files.
#
# If a user uploads a file that has been previously uploaded by another user,
# then the file size will be multiplied by this number when calculating the hit
# towards user's upload limits.
#
# * Setting this value to 1 will effectively disable this feature, as the
#   duplicated file will count for its original size.
#
# * Setting this value to 0 will make dupes ignore the weekly limit.
#
# * Setting to any value between 0 and 1 will decreasethe file's actual size
#   by that factor.
#
# The default is 0.5 as uploads still cost processing power and bandwidth.
DUPE_DECREASE_FACTOR = 0.5

################################################################################

# Discord webhook settings.

# Webhook for notifying admins about malicious file uploads. Only happens when
# virus scans are enabled (`UPLOAD_SCAN` is `True`).
#
# Data posted: user ID, username, filename, file size, and `clamdscan` output.
UPLOAD_SCAN_WEBHOOK = ""

# Webhook for notifying admins about users who get banned.
#
# Data posted:
#
# * For users: user ID, username, reason, and ban period.
#
# * For IPs: IP address, reason, and ban period.
#
# To disable these webhooks, comment the line out (by putting a # before the
# name).
USER_BAN_WEBHOOK = ""
IP_BAN_WEBHOOK = ""

# Webhook for notifying about JPEGs that grow too big after EXIF stripping.
EXIF_TOOBIG_WEBHOOK = ""

# Webhook for notifying about user registrations.
#
# Chef (https://gitlab.com/elixire/chef) can consume the data from this webhook
# and take care of some things for you.
USER_REGISTER_WEBHOOK = ""

################################################################################

# The ratelimits for requests.
#
# The keys are based off of the functions in the blueprint code.
# The special `*` key applies to all requests.
RATELIMITS = {
    "*": (15, 5),
    "fetch.file_handler": (50, 6),
    "fetch.thumbnail_handler": (80, 10),
}

################################################################################

# Enable thumbnail processing?
THUMBNAILS = True

# The path to the thumbnail folder on disk.
THUMBNAIL_FOLDER = "./thumbnails"

# Thumbnail sizes.
THUMBNAIL_SIZES = {
    # large (5000x5000)
    "l": (5000, 5000),
    # medium (1000x1000)
    "m": (1000, 1000),
    # small (500x500)
    "s": (500, 500),
    # tiny (250x250)
    "t": (250, 250),
}
