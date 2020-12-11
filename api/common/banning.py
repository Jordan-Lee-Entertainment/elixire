# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import ipaddress
import logging
import enum
from typing import Union, List, Dict, Any, Optional

from quart import request, current_app as app
from api.common.utils import get_ip_addr
from api.common.webhook import ban_webhook, ip_ban_webhook
from api.storage import calc_ttl
from api.errors import WebhookError, FailedAuth

log = logging.getLogger(__name__)


async def ban_by_ip(
    ip_addr: Union[ipaddress.IPv4Network, ipaddress.IPv6Network], reason: str
) -> None:
    """Ban a given Network."""
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
    except WebhookError as err:
        log.error("failed to contact webhook for ip ban: %r", err)


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
        inet = ipaddress.ip_network(get_ip_addr())
        if isinstance(inet, ipnetwork.IPv6Network):
            inet = inet.supernet(new_prefix=64)

        log.warning(f"Banning ip address {inet} with reason {reason!r}")
        await ban_by_ip(inet, reason)


async def unban_user(user_id: int) -> None:
    await app.storage.raw_invalidate(f"userban:{user_id}")
    await app.db.execute(
        """
        DELETE FROM bans
        WHERE user_id = $1
        """,
        user_id,
    )


async def unban_ip(ipaddr: Union[ipaddress.IPv4Network, ipaddress.IPv6Network]) -> None:
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
    # Can either be a v4, a v6, or an user id.
    target_value: Union[ipaddress.IPv4Network, ipaddress.IPv6Network, int],
    *,
    target_type: TargetType,
    page: int = 0,
    per_page: int = 30,
) -> List[Dict[str, Any]]:
    """Get the bans for a given target (user ID or IP address)."""
    is_user = target_type == TargetType.User

    table = "bans" if is_user else "ip_bans"
    field = "user_id" if is_user else "ip_address"

    rows = await app.db.fetch(
        f"""
        SELECT reason, end_timestamp, timestamp
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


async def check_bans(user_id: Optional[int] = None) -> None:
    """Check if the current user is already banned.

    Raises
    ------
    FailedAuth
        When a user is banned, or their
        IP address is banned.
    """
    if user_id is not None:
        reason = await app.storage.get_ban(user_id)

        if reason:
            raise FailedAuth(f"User is banned. {reason}")

    # we convert whatever quart or cf gives us into a python's ipaddress object
    # which is auto-translated by asyncpg to an inet/cidr postgresql type
    inet = ipaddress.ip_network(get_ip_addr())
    ip_ban_reason = await app.storage.get_ipban(inet)
    if ip_ban_reason:
        raise FailedAuth(f"IP address is banned. {ip_ban_reason}")
