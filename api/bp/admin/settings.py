# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

from quart import Blueprint, current_app as app, request, jsonify

from api.common.auth import token_check, check_admin
from api.errors import BadInput

bp = Blueprint("admin_settings", __name__)


async def get_admin_settings(conn, admin_id: int) -> dict:
    """Get admin settings for a user"""
    row = await conn.fetchrow(
        """
        SELECT audit_log_emails
        FROM admin_user_settings
        WHERE user_id = $1
        """,
        admin_id,
    )

    if row is None:
        await conn.execute(
            """
            INSERT INTO admin_user_settings (user_id)
            VALUES ($1)
            """,
            admin_id,
        )

        return await get_admin_settings(conn, admin_id)

    return dict(row)


@bp.route("", strict_slashes=False)
async def _admin_settings():
    """Get own admin settings."""
    admin_id = await token_check()
    await check_admin(admin_id, True)

    return jsonify(await get_admin_settings(app.db, admin_id))


@bp.route("", methods=["PATCH"], strict_slashes=False)
async def change_admin_settings():
    """Change own admin settings."""
    admin_id = await token_check()
    await check_admin(admin_id, True)

    j = await request.get_json()

    try:
        audit_emails = bool(j["audit_log_emails"])
    except (KeyError, ValueError, TypeError):
        raise BadInput("bad/nonexistant value for audit_log_emails")

    await app.db.execute(
        """
        INSERT INTO admin_user_settings (user_id, audit_log_emails)
        VALUES ($1, $2)

        ON CONFLICT ON CONSTRAINT admin_user_settings_pkey
        DO UPDATE SET
            audit_log_emails = $2
        WHERE admin_user_settings.user_id = $1
        """,
        admin_id,
        audit_emails,
    )

    return "", 204
