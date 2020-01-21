# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import asyncio
import logging
from typing import Optional, Union, Dict, List

from quart import current_app as app

from api.errors import WebhookError

log = logging.getLogger(__name__)


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

    if getattr(app, "_test", False):
        app._webhook_list.append(
            {"webhook_url": webhook_url, "embed": embed, "text": text}
        )

        return

    if not webhook_url:
        log.warning("Ignored webhook, payload=%r", payload)
        return

    async with app.session.post(webhook_url, json=payload) as resp:
        status = resp.status

        if status == 429:
            log.warning("We are being rate-limited.")

            try:
                retry_after = int(resp.headers["retry-after"])
                log.warning("waiting %d ms", retry_after)
                await asyncio.sleep(retry_after / 1000)
                return await _post_webhook(webhook_url, embed=embed, text=text)
            except (ValueError, KeyError):
                pass

            raise WebhookError("Webhook is ratelimited")

        if status == 200:
            return

        try:
            data = await resp.json()
        except Exception as exc:
            data = f"Failed to read/parse JSON ({exc!r})"

        err_code, err_msg = data["code"], data["message"]
        log.warning(
            "Failed to dispatch webhook, status=%d, code=%d, msg=%r",
            status,
            err_code,
            err_msg,
        )

        raise WebhookError(
            f"Failed to send webhook ({status}, {err_code}, {err_msg!r})"
        )


async def ban_webhook(user_id: int, reason: str, period: str):
    """Send a webhook containing banning informatino of a user."""

    username = await app.storage.get_username(user_id)
    return await _post_webhook(
        getattr(app.econfig, "USER_BAN_WEBHOOK", None),
        embed={
            "title": "Elixire Auto Banning",
            "color": 0x696969,
            "fields": [
                {"name": "user", "value": f"id: {user_id}, name: {username}"},
                {"name": "reason", "value": reason},
                {"name": "period", "value": period},
            ],
        },
    )


async def ip_ban_webhook(ip_address: str, reason: str, period: str):
    """Send a webhook containing banning information."""
    return await _post_webhook(
        getattr(app.econfig, "IP_BAN_WEBHOOK", None),
        embed={
            "title": "Elixire Auto IP Banning",
            "color": 0x696969,
            "fields": [
                {"name": "IP address", "value": ip_address},
                {"name": "reason", "value": reason},
                {"name": "period", "value": period},
            ],
        },
    )


async def register_webhook(user_id, username, discord_user, email):
    return await _post_webhook(
        getattr(app.econfig, "USER_REGISTER_WEBHOOK", None),
        embed={
            "title": "user registration webhook",
            "color": 0x7289DA,
            "fields": [
                {"name": "userid", "value": str(user_id)},
                {"name": "user name", "value": username},
                {"name": "discord user", "value": discord_user},
                {"name": "email", "value": email},
            ],
        },
    )


async def jpeg_toobig_webhook(ctx, size_after):
    """Dispatch a webhook when the EXIF checking failed."""
    increase = size_after / ctx.file.size
    username = await app.storage.get_username(ctx.user_id)

    return await _post_webhook(
        getattr(app.econfig, "EXIF_TOOBIG_WEBHOOK", None),
        embed={
            "title": "Elixire EXIF Cleaner Size Change Warning",
            "color": 0x420420,
            "fields": [
                {"name": "user", "value": f"id: {ctx.user_id}, name: {username}"},
                {"name": "in filename", "value": ctx.file.name},
                {"name": "out filename", "value": ctx.shortname},
                {
                    "name": "size change",
                    "value": f"{ctx.file.size}b -> {size_after}b "
                    f"({increase:.01f}x)",
                },
            ],
        },
    )


async def scan_webhook(ctx, scan_out: str):
    """Execute a discord webhook with information about the virus scan."""
    username = await app.storage.get_username(ctx.user_id)

    return await _post_webhook(
        app.econfig.UPLOAD_SCAN_WEBHOOK,
        embed={
            "title": "Elixire Virus Scanning",
            "color": 0xFF0000,
            "fields": [
                {"name": "user", "value": f"id: {ctx.user_id}, username: {username}"},
                {
                    "name": "file info",
                    "value": f"filename: `{ctx.file.name}`, {ctx.file.size} bytes",
                },
                {"name": "clamdscan out", "value": f"```\n{scan_out}\n```"},
            ],
        },
    )
