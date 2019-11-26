# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only
import logging

from quart import request, current_app as app
from api.common import get_ip_addr
from api.common.webhook import ban_webhook, ip_ban_webhook
from api.storage import calc_ttl
from api.errors import WebhookError

log = logging.getLogger(__name__)


async def ban_by_ip(ip_addr: str, reason: str) -> None:
    """Ban a given IP address."""
    period = app.econfig.IP_BAN_PERIOD
    end_timestamp = await app.db.fetchval(
        f"""
        INSERT INTO ip_bans (ip_address, reason, end_timestamp)
        VALUES ($1, $2, now()::timestamp + interval '{period}')
        RETURNING end_timestamp
        """,
        ip_addr,
        reason,
    )

    await app.storage.set_with_ttl(f"ipban:{ip_addr}", reason, calc_ttl(end_timestamp))
    try:
        await ip_ban_webhook(ip_addr, f"[ip ban] {reason}", period)
    except WebhookError:
        pass


async def ban_user(user_id: int, reason: str) -> None:
    """Ban a given user."""
    period = app.econfig.BAN_PERIOD

    end_timestamp = await app.db.fetchval(
        f"""
        INSERT INTO bans (user_id, reason, end_timestamp)
        VALUES ($1, $2, now()::timestamp + interval '{period}')
        RETURNING end_timestamp
        """,
        user_id,
        reason,
    )

    await app.storage.set_with_ttl(
        f"userban:{user_id}", reason, calc_ttl(end_timestamp)
    )
    try:
        await ban_webhook(user_id, reason, period)
    except WebhookError:
        pass


async def ban_request(reason: str) -> None:
    """Ban the given request. Favors user banning when possible, and falls
    back to IP address banning."""
    try:
        username, user_id = request.ctx
        log.warning(f"Banning {username} {user_id} with reason {reason!r}")
        await ban_user(user_id, reason)
    except AttributeError:
        ip_addr = get_ip_addr()
        log.warning(f"Banning ip address {ip_addr} with reason {reason!r}")
        await ban_by_ip(ip_addr, reason)


async def unban_user(user_id: int) -> None:
    await app.storage.raw_invalidate(f"userban:{user_id}")
    await app.db.execute(
        """
        DELETE FROM bans
        WHERE user_id = $1
        """,
        user_id,
    )


async def unban_ip(ipaddr: str) -> None:
    await app.storage.raw_invalidate(f"ipban:{ipaddr}")
    await app.db.execute(
        """
        DELETE FROM ip_bans
        WHERE ip_address = $1
        """,
        ipaddr,
    )
