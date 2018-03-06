"""Common schema information."""

from cerberus import Validator
from .errors import BadInput


def validate(document, schema):
    """Validate one document against a schema."""
    v = Validator(schema)
    if not v.validate(document):
        raise BadInput('Bad payload', v.errors)

    return document


PROFILE_SCHEMA = {
    'password': {'type': 'string'},
    'new_password': {'type': 'string', 'nullable': True},
}
