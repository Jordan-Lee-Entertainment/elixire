# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

LOGGING_LEVEL = "DEBUG"

MAIN_URL = "http://localhost:8000"

USE_HTTPS = False

PORT = 8000

ENABLE_FRONTEND = False

db = {"host": "postgres", "user": "postgres", "password": ""}

redis = "redis://redis"
TOKEN_SECRET = b":\xed\x9d\x19\x1b\xf5\xed\x02\xba12\x97$W\xb7\x9a\x97\xc2\xaf\xa8\xc3\x86\xeeR\xf1lg.\xacWR\x91\xaf|\xcf\xff\xc8\xb0\xccF\x83\x06`\xa7p\xf5B\xb5"

RATELIMITS = {
    # global ratelimit for authenticated connections
    "*": (10000, 1)
}

REQUIRE_ACCOUNT_APPROVALS = False

FORCE_EXTENSION = {"image/jpeg": ".jpg"}
INCLUDE_EXTENSIONS = {"application/octet-stream": [""]}

UPLOAD_SCAN = False
SCAN_WAIT_THRESHOLD = 1
