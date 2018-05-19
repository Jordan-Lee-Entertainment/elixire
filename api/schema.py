"""Common schema information."""
import re

from cerberus import Validator
from .errors import BadInput

USERNAME_REGEX = re.compile(r'^[a-z]{1}[a-zA-Z0-9_]{2,19}$', re.A)
SUBDOMAIN_REGEX = re.compile(r'^[a-zA-Z0-9_-]{0,63}$', re.A)
DISCORD_REGEX = re.compile(r'^[^\#]{2,32}\#\d{4}$', re.A)
EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$', re.A)


class ElixireValidator(Validator):
    """Main validator class for elixire data types."""

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
        return len(value) >= 8 and len(value) < 100

    def _validate_type_subdomain(self, value) -> bool:
        """Validate subdomains."""
        # re.match returns none, soooo, bool(None) = False
        return bool(SUBDOMAIN_REGEX.match(value))

    def _validate_type_discord(self, value: str) -> bool:
        """Validate discord usernames."""
        return bool(DISCORD_REGEX.match(value))

    def _validate_type_email(self, value: str) -> bool:
        return bool(EMAIL_REGEX.match(value))


def validate(document, schema):
    """Validate one document against a schema."""
    validator = ElixireValidator(schema)
    validator.allow_unknown = False

    if not validator.validate(document):
        raise BadInput('Bad payload', validator.errors)

    return document


PROFILE_SCHEMA = {
    'user': {'type': 'string'},
    'password': {'type': 'password', 'required': False},
    'subdomain': {'type': 'subdomain', 'nullable': True},
    'new_password': {'type': 'password', 'nullable': True},
    'domain': {'type': 'integer', 'nullable': True},
    'email': {'type': 'email', 'nullable': True},
    'consented': {'type': 'boolean', 'nullable': True, 'required': False},
}

REGISTRATION_SCHEMA = {
    'username': {'type': 'username', 'required': True},
    'password': {'type': 'password', 'required': True},
    'discord_user': {'type': 'discord', 'required': True},
    'email': {'type': 'email', 'required': True},
}

REVOKE_SCHEMA = {
    # can't use type password here
    'password': {'type': 'string', 'required': True},
}

LOGIN_SCHEMA = {
    'user': {'type': 'string', 'nullable': False, 'required': True},
    'password': {'type': 'string', 'nullable': False, 'required': True},
}

DEACTIVATE_USER_SCHAMA = {
    'confirmation': {'type': 'boolean', 'required': True},
    'password': {'type': 'password', 'required': True},
}
