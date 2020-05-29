# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import logging

from quart import Blueprint, current_app as app, jsonify

from api.common.auth import token_check
from api.scheduled_deletes import ScheduledDeleteQueue


bp = Blueprint("scheduled_deletes", __name__)
log = logging.getLogger(__name__)

# XXX: write API
