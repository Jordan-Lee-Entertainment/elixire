# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

# elixire instance configuration file
# Please read over all the available options.
# There are a lot of configuration options. Please
# take your time going through each one of them

# === BASIC SETTINGS ===
INSTANCE_NAME = "elixi.re"
MAIN_URL = "https://elixi.re"
MAIN_INVITE = "https://discord.gg/123456"
SUPPORT_EMAIL = "support@elixi.re"

# If URLs over the API show http or https by default.
USE_HTTPS = True

# Mailgun API credentials for instance emails.
# (Account deletion, Data Dump, etc.)
MAILGUN_DOMAIN = ""
MAILGUN_API_KEY = ""

# Link / to ./frontend and /admin to ./admin-panel ?
ENABLE_FRONTEND = True

# Which folder to store uploaded images to?
IMAGE_FOLDER = "./images"

# Folder to store data dumps.
DUMP_ENABLED = True
DUMP_FOLDER = "./dumps"

# The dump janitor checks the directory
# for files that are over 6 hours long and deletes them
# to save space.
#
# It runs every DUMP_JANITOR_PERIOD seconds checking for files.
DUMP_JANITOR_PERIOD = 600

# Postgres credentials
db = {
    "host": "localhost",
    "user": "postgres",
    "password": "",
    # 'database': 'dab'
}

# Redis URL
redis = "redis://localhost"

# d1 configuration, generate a key with:
#  >>> from cryptography.fernet import Fernet
#  >>> Fernet.generate_key()
#
# Use the same generated key on d1.
# Set as None to keep d1-specific routes disabled.
SECRET_KEY = None

# Token shared secret.
# this is used to keep more security
# around api tokens.
#
# **DO NOT LET ANYONE KNOW THIS SECRET.**
#
# to generate a valid key, spawn python and then:
#  >>> from os import urandom
#  >>> urandom(48)
#  b'<some random results here>'
TOKEN_SECRET = b""

# How many seconds to keep timed tokens valid?
# default value is 72 hours = 3 days.
TIMED_TOKEN_AGE = 259200

# === METRICS ===

# Enable metrics?
# uses InfluxDB and aioinflux to send data.
ENABLE_METRICS = False
METRICS_DATABASE = "elixire"

# InfluxDB Authentication, if any
INFLUXDB_AUTH = False
INFLUX_HOST = ("localhost", 8086)
INFLUX_SSL = False
INFLUX_USER = "admin"
INFLUX_PASSWORD = "123"

# ADVANCED:
# This defines the limits for the main metrics worker.
# Instead of sending a datapoint to InfluxDB every time
# there is one, we schedule a maximum of METRICS_LIMIT[0]
# datapoints to be sent every METRICS_LIMIT[1] seconds,
# in order.
METRICS_LIMIT = (100, 3)

# === METRICS COMPACTION ===
# Do not change those unless you know
# what you're doing.
#
# Metrics compaction is defined in issue 78,
# where i'm talking about a task that
# compacts large amounts of datapoints
# for historical purposes.

# METRICS_COMPACT_GENERALIZE sets the amount of
# time, in seconds, that the compactor task
# will split datapoints into.
#
# It is set to 1 hour, so all things such as
# per-second `request` / `response` will become
# `request_hour` and `response_hour`
METRICS_COMPACT_GENERALIZE = 3600

# METRICS_COMPACT_KEEP_POINTS sets the maximum
# amount of time pre-compacted datapoints
# can still lay around before getting cleaned.
#
# By default it is set to 10 days, but it can
# be changed if your grafana instance is starting to
# have problems with the amount of data
METRICS_COMPACT_KEEP_POINTS = 10 * 86400

# === RATELIMIT BANNING SETTINGS ===

# change this to your wanted ban period
# valid: '1 day', '6 hours', '10 seconds', etc.
BAN_PERIOD = "6 hours"
IP_BAN_PERIOD = "5 minutes"

# How many ratelimits can be triggered by
# a client before they get banned?
RL_THRESHOLD = 10

# === UPLOAD SETTINGS ===
# Configurations here are mixed for images/shortens.

# Sets the minimum shortname length (for both image uploads
# and shortens)
SHORTNAME_LEN = 3

# Maximum length of the URL that's going to be shortened
MAX_SHORTEN_URL_LEN = 250

# run clamdscan on every upload.
# this will use the multicore option,
# so it is not recommended on low-end machines.
UPLOAD_SCAN = False

# How many seconds to wait scanning before
# switching that scan to the background? (can be int or float)
#
# See issue #35 for more details.
SCAN_WAIT_THRESHOLD = 1

# Should we clear EXIF values for JPEGs?
# Needs Pillow (should be already installed by requirements.txt)
CLEAR_EXIF = False

# To prevent potential exploits to take over a lot of storage space
# by abusing EXIF cleaning, we're comparing size of images before and after
# EXIF cleaning. If exif_cleaned_filesize/regular_filesize is bigger than
# the following number, we just use non-exif cleaned versions of the files.
# Using anything below 1.25 or so might cause false positives.
# Set CLEAR_EXIF to False to disable cleaning
EXIF_INCREASELIMIT = 2

# Accepted MIME types for uploading.
# NOTE: MIME type checking is ignored for admins.
ACCEPTED_MIMES = [
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/webp",
    "image/svg+xml",
    "audio/webm",
    "video/webm",
]


# Decrease factor for duplicated.
# If a user sends a file that another user has sent previously,
# then it won't count as much towards their limit.
#
# Setting this value to 1 will disable the feature.
# Setting this value to 0 will make dupes ignore the weekly limit
# Setting to any value between 0 and 1 will decrease
# the file's actual size by that factor
#
# Default is 0.5 as the upload still costs processing power and bandwidth
DUPE_DECREASE_FACTOR = 0.5


# === WEBHOOK SETTINGS ===
# All webhooks here are Discord Webhooks.

# When UPLOAD_SCAN is true and
# a file is detected as being malicious,
# we will call this discord webhook
# with data about the upload.
UPLOAD_SCAN_WEBHOOK = ""

# Webhook for banned users.
# Comment the line to disable those webhooks.
USER_BAN_WEBHOOK = ""
IP_BAN_WEBHOOK = ""

# Webhook for JPEGs that grew too much after EXIF cleaning.
EXIF_TOOBIG_WEBHOOK = ""

# Webhook for user registrations.
USER_REGISTER_WEBHOOK = ""

# === RATELIMIT SETTINGS ===

RATELIMITS = {
    "*": (15, 5),
    "fetch.file_handler": (50, 6),
    "fetch.thumbnail_handler": (80, 10),
}

# === THUMBNAIL SETTINGS ===

# Enable thumbnails?
THUMBNAILS = True
THUMBNAIL_FOLDER = "./thumbnails"

# Thumbnail sizing
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

# === FEATURE SETTINGS ===
# Disabled features will raise a 503 to
# whoever requests the route

# Can be used for private instances to disable
# registrations, or for an instance with heavy load
# to disable it for debug.

UPLOADS_ENABLED = True
SHORTENS_ENABLED = True
REGISTRATIONS_ENABLED = True

# Enable users to change their own profile information?
PATCH_API_PROFILE_ENABLED = True

# Enable notifications for user activation?
NOTIFY_ACTIVATION_EMAILS = True
