async def ban_webhook(app, user_id: int, reason: str, period: str):
    """Send a webhook containing banning information."""
    wh_url = getattr(app.econfig, 'USER_BAN_WEBHOOK', None)
    if not wh_url:
        return

    if isinstance(user_id, int):
        uname = await app.db.fetchval("""
            select username
            from users
            where user_id = $1
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

    async with app.session.post(wh_url,
                                json=payload) as resp:
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

    async with app.session.post(wh_url,
                                json=payload) as resp:
        return resp


async def register_webhook(app, wh_url, user_id, username, discord_user, email):
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
