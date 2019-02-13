# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

from sanic import response

def resp_empty():
    """Return an empty response, with 204."""
    return response.text('', status=204)
