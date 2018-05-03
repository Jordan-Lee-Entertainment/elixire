"""Common schema information."""
import re

from cerberus import Validator
from .errors import BadInput

USERNAME_REGEX = re.compile(r'^[a-z]{1}[a-zA-Z0-9_]{2,19}$', re.M | re.A)

class ElixireValidator(Validator):
    def _validate_type_username(self, value) -> bool:
        """Validate usernames."""
        # re.match returns none, soooo, bool(None) = False
        return bool(USERNAME_REGEX.match(value))

    def _validate_type_password(self, value) -> bool:
        """Validate passwords.

         - More than 8 characters.
         - Less than 100.
        """
        # Would it be interesting to measure entropy?
        return len(value) > 8 and len(value) < 100

def validate(document, schema):
    """Validate one document against a schema."""
    validator = ElixireValidator(schema)
    if not validator.validate(document):
        raise BadInput('Bad payload', validator.errors)

    return document


PROFILE_SCHEMA = {
    'user': {'type': 'string'},
    'password': {'type': 'string'},
    'new_password': {'type': 'string', 'nullable': True},
    'domain': {'type': 'integer', 'nullable': True},
}

REGISTRATION_SCHEMA = {
    'username': {'type': 'username'},
    'password': {'type': 'password'},
    'discord_user': {'type': 'string'},
}
