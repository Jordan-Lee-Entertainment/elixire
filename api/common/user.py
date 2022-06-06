# elixire: Image Host software
# Copyright 2018-2022, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

from typing import Dict, Union

from quart import current_app as app

from api.common.auth import pwd_hash
from api.snowflake import get_snowflake


async def create_user(
    *, username: str, password: str, email: str, active: bool = True
) -> Dict[str, Union[str, int]]:
    """Creates a single user. Outputs a dictionary containing the user's
    newly generated ID and password hash."""

    user_id = get_snowflake()
    password_hash = await pwd_hash(password)

    await app.db.execute(
        """
        INSERT INTO users (user_id, username, password_hash, email, active)
        VALUES ($1, $2, $3, $4, $5)
        """,
        user_id,
        username,
        password_hash,
        email,
        active,
    )

    await app.db.execute(
        """
        INSERT INTO limits (user_id) VALUES ($1)
        """,
        user_id,
    )

    # invalidate to round the case where they (tried to) loginin before register
    await app.storage.raw_invalidate(f"uid:{username}")

    return {"user_id": user_id, "password_hash": password_hash}
