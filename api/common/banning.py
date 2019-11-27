# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import logging
import enum
from typing import Union, List, Dict, Any

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


class TargetType(enum.Enum):
    User = "user"
    Ip = "ip"


async def get_bans(
    target_value: Union[str, int],
    *,
    target_type: TargetType,
    page: int = 0,
    per_page: int = 30,
) -> List[Dict[str, Any]]:
    """Get the bans for a given target (user ID or IP address)."""
    is_user = target_type == TargetType.User

    table = "bans" if is_user else "ip_bans"
    field = "user_id" if is_user else "ip_address"

    # TODO make bans table have timestamp column
    maybe_ts = "" if is_user else ", timestamp"

    rows = await app.db.fetch(
        f"""
        SELECT reason, end_timestamp {maybe_ts}
        FROM {table}
        WHERE {field} = $1
        ORDER BY end_timestamp DESC
        LIMIT {per_page}
        OFFSET ({per_page} * $2)
        """,
        target_value,
        page,
    )

    return list(map(dict, rows))
