# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import logging
import asyncio
from typing import Optional, Union, Dict, List

from quart import current_app as app

log = logging.getLogger(__name__)


class WebhookError(Exception):
    pass


async def _do_post_webhook(webhook_url: str, json_payload: Dict) -> None:
    log.debug("sending webhook with payload %r", json_payload)
    async with app.session.post(webhook_url, json=json_payload) as resp:
        status = resp.status

        if status == 429:
            log.warning("We are being rate-limited.")

            maybe_retry_after = resp.headers.get("retry-after")
            try:
                retry_after = int(maybe_retry_after)
            except ValueError:
                raise WebhookError("Webhook is ratelimited")

            log.warning("waiting %d ms", retry_after)
            await asyncio.sleep(retry_after / 1000)
            return await _do_post_webhook(webhook_url, json_payload)

        if status in (200, 204):
            return

        data = await resp.read()
        log.warning("Failed to dispatch webhook, status=%d, data=%r", status, data)
        raise WebhookError(f"Failed to send webhook ({status}, {data!r})")


async def _post_webhook(
    webhook_url: Optional[str],
    *,
    embed: Optional[dict] = None,
    text: Optional[str] = None,
) -> None:
    """Post to the given webhook."""
    payload: Dict[str, Union[str, List[dict]]] = {}

    if embed is not None:
        if isinstance(embed, list):
            payload["embeds"] = embed
        else:
            payload["embeds"] = [embed]

    if text is not None:
        payload["content"] = text

    if not embed and not text:
        raise TypeError("Either text or embed must be provided.")

    if not webhook_url:
        log.warning("Ignored webhook, payload=%r", payload)
        return

    await _do_post_webhook(webhook_url, payload)


async def ban_webhook(user_id: int, reason: str, period: str):
    """Send a webhook containing banning information."""
    wh_url = getattr(app.econfig, "USER_BAN_WEBHOOK", None)
    if not wh_url:
        return

    if isinstance(user_id, int):
        uname = await app.db.fetchval(
            """
            SELECT username
            FROM users
            WHERE user_id = $1
        """,
            user_id,
        )
    else:
        uname = "<no username found>"

    payload = {
        "title": "Elixire Auto Banning",
        "color": 0x696969,
        "fields": [
            {"name": "user", "value": f"id: {user_id}, name: {uname}"},
            {
                "name": "reason",
                "value": reason,
            },
            {
                "name": "period",
                "value": period,
            },
        ],
    }

    await _post_webhook(wh_url, embed=payload)


async def ip_ban_webhook(ip_address: str, reason: str, period: str):
    """Send a webhook containing banning information."""
    wh_url = getattr(app.econfig, "IP_BAN_WEBHOOK", None)
    if not wh_url:
        return

    payload = {
        "title": "Elixire Auto IP Banning",
        "color": 0x696969,
        "fields": [
            {
                "name": "IP address",
                "value": ip_address,
            },
            {
                "name": "reason",
                "value": reason,
            },
            {
                "name": "period",
                "value": period,
            },
        ],
    }

    await _post_webhook(wh_url, embed=payload)


async def register_webhook(
    wh_url: str, user_id: int, username: str, discord_user: str, email: str
) -> None:
    # call webhook
    payload = {
        "title": "user registration webhook",
        "color": 0x7289DA,
        "fields": [
            {
                "name": "userid",
                "value": str(user_id),
            },
            {
                "name": "user name",
                "value": username,
            },
            {
                "name": "discord user",
                "value": discord_user,
            },
            {
                "name": "email",
                "value": email,
            },
        ],
    }
    await _post_webhook(wh_url, embed=payload)


async def jpeg_toobig_webhook(ctx, size_after):
    """Dispatch a webhook when the EXIF checking raised
    stuff.
    """
    wh_url = getattr(app.econfig, "EXIF_TOOBIG_WEBHOOK", None)
    if not wh_url:
        return

    increase = size_after / ctx.file.size

    uname = await app.db.fetchval(
        """
        SELECT username
        FROM users
        WHERE user_id = $1
    """,
        ctx.user_id,
    )

    payload = {
        "title": "Elixire EXIF Cleaner Size Change Warning",
        "color": 0x420420,
        "fields": [
            {"name": "user", "value": f"id: {ctx.user_id}, name: {uname}"},
            {
                "name": "in filename",
                "value": ctx.file.name,
            },
            {
                "name": "out filename",
                "value": ctx.shortname,
            },
            {
                "name": "size change",
                "value": f"{ctx.file.size}b -> {size_after}b " f"({increase:.01f}x)",
            },
        ],
    }
    await _post_webhook(wh_url, embed=payload)


async def scan_webhook(ctx, scan_out: str):
    """Execute a discord webhook with information about the virus scan."""
    uname = await app.db.fetchval(
        """
        SELECT username
        FROM users
        WHERE user_id = $1
    """,
        ctx.user_id,
    )

    payload = {
        "title": "Elixire Virus Scanning",
        "color": 0xFF0000,
        "fields": [
            {"name": "user", "value": f"id: {ctx.user_id}, username: {uname}"},
            {
                "name": "file info",
                "value": f"filename: `{ctx.file.name}`, {ctx.file.size} bytes",
            },
            {"name": "clamdscan out", "value": f"```\n{scan_out}\n```"},
        ],
    }

    await _post_webhook(app.econfig.UPLOAD_SCAN_WEBHOOK, embed=payload)
