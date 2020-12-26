# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

"""
elixi.re - schema data
    mostly containing regexes and schemas for cerberus
"""
import re

import dateutil.parser
from cerberus import Validator

from api.errors import BadInput
from api.enums import AuthDataType

# TODO: cerberus has support for a 'regex' key, which would remove the amount
# of methods inside ElixireValidator.
#
# I do not know the internal implementation of cerberus for custom types,
# but it is likely it's doing something equivalent to getattr() to turn type
# strings into method calls. getattr() is very innefficient/discouraged in
# python.
#
# getattr() sources:
#  https://stackoverflow.com/questions/12798653/does-setattr-and-getattr-slow-down-the-speed-dramatically/12846965
#  https://calidae.blog/to-get-or-not-getattr-with-or-without-attr-17ffa03939d2
#
# source for cerberus 'regex':
#  https://gitlab.com/ratelimited.me/backend/api/-/blob/49b3b959902dbe1ada7f6f7c7c17cae02ccfb002/api/schema.py
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
    "name": {"type": "username", "required": False, "coerce": str.lower},
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
    "name": {"type": "username", "required": True, "coerce": str.lower},
    "password": {"type": "password", "required": True},
    "discord_user": {"type": "discord", "required": True},
    "email": {"type": "email", "required": True},
}

AUTHDATA_PASSWORD_SCHEMA = {
    "password": {"type": "string", "nullable": False, "required": True},
}

AUTHDATA_TOTP_SCHEMA = {
    **AUTHDATA_PASSWORD_SCHEMA,
    **{
        "totp_code": {"type": "string", "nullable": False, "required": True},
    },
}

AUTHDATA_WEBAUTHN_SCHEMA = {
    # 'password' is only required if the challenge is passwordless.
    "password": {"type": "string", "required": False},
    "challenge_id": {"type": "string", "required": True},
    "credential_id": {"type": "string", "required": True},
    "client_data_json": {"type": "string", "required": True},
    "authenticator_data": {"type": "string", "required": True},
    "signature": {"type": "string", "required": True},
}

AUTH_SCHEMA = {
    "username": {
        "type": "string",
        "nullable": False,
        "required": True,
        "coerce": str.lower,
    },
    "authdata_type": {"coerce": lambda x: AuthDataType(x), "required": True},
    "authdata": {
        "anyof": [
            {"type": "dict", "schema": AUTHDATA_PASSWORD_SCHEMA},
            {"type": "dict", "schema": AUTHDATA_WEBAUTHN_SCHEMA},
            {"type": "dict", "schema": AUTHDATA_TOTP_SCHEMA},
        ]
    },
}


DEACTIVATE_USER_SCHEMA = {"password": {"type": "password", "required": True}}

PASSWORD_RESET_SCHEMA = {
    "name": {"type": "string", "required": True, "coerce": str.lower}
}

PASSWORD_RESET_CONFIRM_SCHEMA = {
    "token": {"type": "string", "required": True},
    "new_password": {"type": "password", "required": True},
}

ADMIN_PUT_DOMAIN = {
    "domain": {"type": "string", "required": True},
    "tags": {"type": "list", "schema": {"coerce": int}, "required": False},
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
    "tags": {"type": "list", "schema": {"coerce": int}, "required": False},
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


def isotimestamp_or_int(value: str):
    try:
        return int(value)
    except ValueError:
        return dateutil.parser.isoparse(value)


PURGE_ALL_BASE_SCHEMA = {
    "delete_files_before": {"coerce": isotimestamp_or_int, "required": False},
    "delete_files_after": {"coerce": isotimestamp_or_int, "required": False},
    "delete_shortens_before": {"coerce": isotimestamp_or_int, "required": False},
    "delete_shortens_after": {"coerce": isotimestamp_or_int, "required": False},
    "delete_from_domain": {"coerce": int, "required": False},
}

PURGE_ALL_SCHEMA = {
    **{"password": {"type": "password", "required": True}},
    **PURGE_ALL_BASE_SCHEMA,
}
