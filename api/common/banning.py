# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import logging
from enum import auto, Enum
from quart import current_app as app, request

from .common import get_ip_addr
from api.common.webhook import ban_webhook
from api.errors import FailedAuth

log = logging.getLogger(__name__)

__all__ = ("check_bans", "on_ban")


class BanEntityKind(Enum):
    user_id = auto()
    ip_address = auto()


class BanEntity:
    def __init__(self, kind, data):
        self.kind = kind
        self.data = data

    def __repr__(self):
        return f"BanEntity<kind={self.kind}, data={self.data}>"


async def check_bans(user_id: int):
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

    ip_addr = get_ip_addr()
    ip_ban_reason = await app.storage.get_ipban(ip_addr)
    if ip_ban_reason:
        raise FailedAuth(f"IP address is banned. {ip_ban_reason}")


async def ban_someone(ban_entity: BanEntity, reason: str):
    log.warning("Banning %r with reason %r", ban_entity, reason)

    if ban_entity.kind == BanEntityKind.ip_address:
        ip_address = ban_entity.data
        ban_period = app.econfig.IP_BAN_PERIOD
        await app.db.execute(
            f"""
        INSERT INTO ip_bans (ip_address, reason, end_timestamp)
        VALUES ($1, $2, now()::timestamp + interval '{ban_period}')
        """,
            ip_address,
            reason,
        )

        await app.storage.raw_invalidate(f"ipban:{ip_address}")
    elif ban_entity.kind == BanEntityKind.user_id:
        username, _ = request._user
        user_id = ban_entity.data
        log.warning("\ttip: uid %d is username %r", ban_entity.data, username)

        ban_period = app.econfig.BAN_PERIOD
        await app.db.execute(
            f"""
        INSERT INTO bans (user_id, reason, end_timestamp)
        VALUES ($1, $2, now()::timestamp + interval '{ban_period}')
        """,
            user_id,
            reason,
        )

        await app.storage.raw_invalidate(f"userban:{user_id}")
    else:
        raise AssertionError("Invalid BanEntityKind")

    await ban_webhook(ban_entity, reason, ban_period)


async def on_ban(exception):
    scode = exception.status_code
    reason = exception.args[0]

    try:
        _username, user_id = request._user
        ban_entity = BanEntity(BanEntityKind.user_id, user_id)
    except AttributeError:
        ban_entity = BanEntity(BanEntityKind.ip_address, get_ip_addr())

    ban_lock = app.locks["bans"][ban_entity.data]

    # generate error message before anything
    res = {
        "error": True,
        "code": scode,
        "message": reason,
    }

    res.update(exception.get_payload())
    resp = (res, scode)

    if ban_lock.locked():
        log.warning("Ban lock already acquired.")
        return resp

    async with ban_lock:
        await ban_someone(ban_entity, reason)

    return resp
