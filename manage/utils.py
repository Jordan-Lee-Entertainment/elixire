from .errors import PrintException


async def get_user(ctx, username: str) -> int:
    user_id = await ctx.db.fetchval("""
    SELECT user_id
    FROM users
    WHERE username = $1
    """, username)

    if not user_id:
        raise PrintException('no user found')

    return user_id
