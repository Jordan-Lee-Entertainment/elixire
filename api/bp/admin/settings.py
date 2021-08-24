# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

from sanic import Blueprint, response

from api.decorators import admin_route
from api.errors import BadInput

bp = Blueprint("admin_settings")


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


@bp.get("/api/admin/settings")
@admin_route
async def _admin_settings(request, admin_id):
    """Get own admin settings."""
    return response.json(await get_admin_settings(request.app.db, admin_id))


@bp.patch("/api/admin/settings")
@admin_route
async def change_admin_settings(request, admin_id):
    """Change own admin settings."""
    try:
        audit_emails = bool(request.json["audit_log_emails"])
    except (KeyError, ValueError, TypeError):
        raise BadInput("bad/nonexistant value for audit_log_emails")

    await request.app.db.execute(
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

    return response.text("", status=204)
