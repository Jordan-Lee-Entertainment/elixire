# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

async def ban_webhook(app, user_id: int, reason: str, period: str):
    """Send a webhook containing banning information."""
    wh_url = getattr(app.econfig, 'USER_BAN_WEBHOOK', None)
    if not wh_url:
        return

    if isinstance(user_id, int):
        uname = await app.db.fetchval("""
            SELECT username
            FROM users
            WHERE user_id = $1
        """, user_id)
    else:
        uname = '<no username found>'

    payload = {
        'embeds': [{
            'title': 'Elixire Auto Banning',
            'color': 0x696969,
            'fields': [
                {
                    'name': 'user',
                    'value': f'id: {user_id}, name: {uname}'
                },
                {
                    'name': 'reason',
                    'value': reason,
                },
                {
                    'name': 'period',
                    'value': period,
                }
            ]
        }]
    }

    async with app.session.post(wh_url, json=payload) as resp:
        return resp


async def ip_ban_webhook(app, ip_address: str, reason: str, period: str):
    """Send a webhook containing banning information."""
    wh_url = getattr(app.econfig, 'IP_BAN_WEBHOOK', None)
    if not wh_url:
        return

    payload = {
        'embeds': [{
            'title': 'Elixire Auto IP Banning',
            'color': 0x696969,
            'fields': [
                {
                    'name': 'IP address',
                    'value': ip_address,
                },
                {
                    'name': 'reason',
                    'value': reason,
                },
                {
                    'name': 'period',
                    'value': period,
                }
            ]
        }]
    }

    async with app.session.post(wh_url, json=payload) as resp:
        return resp


async def register_webhook(app, wh_url, user_id,
                           username, discord_user, email):
    # call webhook
    payload = {
        'embeds': [{
            'title': 'user registration webhook',
            'color': 0x7289da,
            'fields': [
                {
                    'name': 'userid',
                    'value': str(user_id),
                },
                {
                    'name': 'user name',
                    'value': username,
                },
                {
                    'name': 'discord user',
                    'value': discord_user,
                },
                {
                    'name': 'email',
                    'value': email,
                }
            ]
        }]
    }

    async with app.session.post(wh_url, json=payload) as resp:
        return resp.status == 200


async def jpeg_toobig_webhook(app, ctx, size_after):
    """Dispatch a webhook when the EXIF checking raised
    stuff.
    """
    wh_url = getattr(app.econfig, 'EXIF_TOOBIG_WEBHOOK', None)
    if not wh_url:
        return

    increase = size_after / ctx.file.size

    uname = await app.db.fetchval("""
        SELECT username
        FROM users
        WHERE user_id = $1
    """, ctx.user_id)

    payload = {
        'embeds': [{
            'title': 'Elixire EXIF Cleaner Size Change Warning',
            'color': 0x420420,
            'fields': [
                {
                    'name': 'user',
                    'value': f'id: {ctx.user_id}, name: {uname}'
                },
                {
                    'name': 'in filename',
                    'value': ctx.file.name,
                },
                {
                    'name': 'out filename',
                    'value': ctx.shortname,
                },
                {
                    'name': 'size change',
                    'value': f'{ctx.file.size}b -> {size_after}b '
                             f'({increase:.01f}x)',
                }
            ]
        }]
    }

    async with app.session.post(wh_url, json=payload) as resp:
        return resp


async def scan_webhook(app, ctx, scan_out: str):
    """Execute a discord webhook with information about the virus scan."""
    uname = await app.db.fetchval("""
        SELECT username
        FROM users
        WHERE user_id = $1
    """, ctx.user_id)

    webhook_payload = {
        'embeds': [{
            'title': 'Elixire Virus Scanning',
            'color': 0xff0000,
            'fields': [
                {
                    'name': 'user',
                    'value': f'id: {ctx.user_id}, username: {uname}'
                },

                {
                    'name': 'file info',
                    'value': f'filename: `{ctx.file.name}`, {ctx.file.size} bytes'
                },

                {
                    'name': 'clamdscan out',
                    'value': f'```\n{scan_out}\n```'
                }
            ]
        }],
    }

    async with app.session.post(app.econfig.UPLOAD_SCAN_WEBHOOK,
                                json=webhook_payload) as resp:
        return resp
