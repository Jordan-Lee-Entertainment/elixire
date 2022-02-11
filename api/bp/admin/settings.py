# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

from quart import Blueprint, jsonify, current_app as app, request

from api.decorators import admin_route
from api.errors import BadInput

bp = Blueprint("admin_settings", __name__)


async def get_admin_settings(admin_id: int) -> dict:
    """Get admin settings for a user"""
    row = await app.db.fetchrow(
        """
    SELECT audit_log_emails
    FROM admin_user_settings
    WHERE user_id = $1
    """,
        admin_id,
    )

    if row is None:
        await app.db.execute(
            """
        INSERT INTO admin_user_settings (user_id)
        VALUES ($1)
        """,
            admin_id,
        )

        return await get_admin_settings(admin_id)

    return dict(row)


@bp.get("/settings")
@admin_route
async def _admin_settings(admin_id):
    """Get own admin settings."""
    return jsonify(await get_admin_settings(admin_id))


@bp.patch("/settings")
@admin_route
async def change_admin_settings(admin_id):
    """Change own admin settings."""
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
