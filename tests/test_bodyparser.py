# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

from sanic.request import Request
from multidict import CIMultiDict
import pytest

from ..api.bp.misc import bodyparser
from ..api.errors import BadInput
from ..api import schema

equivalent_dict = {
    "foo": True,
    "bar": "baz",
    "foobar": "barfoo"
}
equivalent_urlencoded = b"foo=True&bar=baz&foobar=barfoo"
equivalent_json = b'{"foo":true,"bar":"baz","foobar":"barfoo"}'

# We really don't need to hook much up
def create_urlencoded_request():
    request = Request(bytes("/", "utf8"), CIMultiDict([
        ("content-type", "application/x-www-form-urlencoded")
    ]), None, "POST", None)
    request.body = equivalent_urlencoded
    return request

def create_garbage_request(ambiguous=False):
    headers = CIMultiDict()
    if not ambiguous:
        headers["content-type"] = "application/octet-stream"
    
    request = Request(bytes("/", "utf8"), headers, None, "POST", None)
    request.body = equivalent_urlencoded
    return request

def create_json_request(ambiguous=False):
    headers = CIMultiDict()
    if not ambiguous:
        headers["content-type"] = "application/json"
    
    request = Request(bytes("/", "utf8"), headers, None, "POST", None)
    request.body = equivalent_json
    return request

# Test the testing environment essentially
def test_validation():
    validate_body(equivalent_dict)

    with pytest.raises(BadInput) as e_info:
        validate_body({"foo":False, "bar":"baz", "foobar":"barfoo"})

def test_formdata_parsing():    
    request = create_urlencoded_request()
    bodyparser(request)

    validate_body(request.body)

def test_json_parsing():
    request = create_json_request()
    bodyparser(request)

    validate_body(request.body)

def test_json_ambiguous_parsing():
    request = create_json_request(True)
    bodyparser(request)

    validate_body(request.body)

def test_invalid_ambiguous_parsing():
    request = create_garbage_request(True)
    bodyparser(request)

    assert isinstance(request.body, dict) == False

def test_invalid_parsing():
    request = create_garbage_request(False)
    bodyparser(request)

    assert isinstance(request.body, dict) == False

def validate_body(doc):
    schema.validate(doc, {
        "foo": {"type": "boolean", "required": True, "coerce": bool, "allowed": [True]},
        "bar": {"type": "string", "required": True, "allowed": ["baz"]},
        "foobar": {"type": "string", "required": True}
    })
