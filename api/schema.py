# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

"""
elixi.re - schema data
    mostly containing regexes and schemas for cerberus
"""
import re

from cerberus import Validator
from api.errors import BadInput

USERNAME_REGEX = re.compile(r"^[a-zA-Z0-9]{1}[a-zA-Z0-9_]{2,19}$", re.A)
SUBDOMAIN_REGEX = re.compile(r"^([a-z0-9_][a-z0-9_-]{0,61}[a-z0-9_]|[a-z0-9_]|)$", re.A)
DISCORD_REGEX = re.compile(r"^[^\#]{2,70}\#\d{4}$", re.A)
EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", re.A)


class ElixireValidator(Validator):
    """Main validator class for elixire data types."""

    def _validate_type_username(self, value) -> bool:
        """Validate usernames."""
        # re.match returns none, soooo, bool(None) = False
        return bool(USERNAME_REGEX.match(value))

    def _validate_type_password(self, value) -> bool:
        """Validate passwords.

         - More than 8 characters.
         - Equal to or less than 72 bytes.
        """
        # TODO: Would it be interesting to measure entropy?
        return len(value) >= 8 and len(value.encode()) <= 72

    def _validate_type_subdomain(self, value) -> bool:
        """Validate subdomains."""
        # re.match returns none, soooo, bool(None) = False
        return bool(SUBDOMAIN_REGEX.match(value))

    def _validate_type_discord(self, value: str) -> bool:
        """Validate discord usernames."""
        return bool(DISCORD_REGEX.match(value))

    def _validate_type_email(self, value: str) -> bool:
        return bool(EMAIL_REGEX.match(value))

    def _validate_type_snowflake(self, value: str):
        try:
            int(value)
            return True
        except ValueError:
            return False


def validate(document, schema):
    """Validate one document against a schema."""
    validator = ElixireValidator(schema)
    validator.allow_unknown = False

    if not validator.validate(document):
        raise BadInput("Bad payload", validator.errors)

    return validator.document


PATCH_PROFILE = {
    "username": {"type": "username", "required": False, "coerce": str.lower},
    "password": {"type": "password", "required": False},
    "email": {"type": "email", "required": False},
    "domain": {"type": "integer", "required": False},
    "subdomain": {"type": "subdomain", "required": False, "nullable": True},
    "shorten_domain": {"type": "integer", "required": False, "nullable": True},
    "shorten_subdomain": {"type": "subdomain", "required": False, "nullable": True},
    "new_password": {"type": "password", "required": False, "nullable": True},
    "consented": {"type": "boolean", "required": False, "nullable": True},
    "paranoid": {"type": "boolean", "required": False},
}

REGISTRATION_SCHEMA = {
    "username": {"type": "username", "required": True, "coerce": str.lower},
    "password": {"type": "password", "required": True},
    "discord_user": {"type": "discord", "required": True},
    "email": {"type": "email", "required": True},
}

REVOKE_SCHEMA = {
    "user": {
        "type": "string",
        "nullable": False,
        "required": True,
        "coerce": str.lower,
    },
    "password": {"type": "string", "required": True},
}

LOGIN_SCHEMA = {
    "user": {
        "type": "string",
        "nullable": False,
        "required": True,
        "coerce": str.lower,
    },
    "password": {"type": "string", "nullable": False, "required": True},
}

DEACTIVATE_USER_SCHEMA = {"password": {"type": "password", "required": True}}

PASSWORD_RESET_SCHEMA = {
    "username": {"type": "string", "required": True, "coerce": str.lower}
}

PASSWORD_RESET_CONFIRM_SCHEMA = {
    "token": {"type": "string", "required": True},
    "new_password": {"type": "password", "required": True},
}

ADMIN_PUT_DOMAIN = {
    "domain": {"type": "string", "required": True},
    "admin_only": {"type": "boolean", "required": True},
    "official": {"type": "boolean", "required": True},
    "permissions": {"coerce": int, "required": False, "default": 3},
    "owner_id": {"coerce": int, "required": False},
}

ADMIN_MODIFY_FILE = {
    "domain_id": {"type": "integer", "required": False},
    "shortname": {"type": "string", "required": False},
}

ADMIN_MODIFY_USER = {
    "email": {"type": "string", "required": False},
    "upload_limit": {"type": "integer", "required": False},
    "shorten_limit": {"type": "integer", "required": False},
}

ADMIN_MODIFY_DOMAIN = {
    "owner_id": {"coerce": int, "required": False},
    "admin_only": {"type": "boolean", "required": False},
    "official": {"type": "boolean", "required": False},
    "permissions": {"coerce": int, "required": False},
}

ADMIN_SEND_DOMAIN_EMAIL = {
    "subject": {"type": "string", "required": True},
    "body": {"type": "string", "required": True},
}

ADMIN_SEND_BROADCAST = {
    "subject": {"type": "string", "required": True},
    "body": {"type": "string", "required": True},
}

RECOVER_USERNAME = {"email": {"type": "email", "required": True}}
