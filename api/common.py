import string
import secrets

import itsdangerous

VERSION = '2.0.0'
ALPHABET = string.ascii_lowercase + string.digits


class TokenType:
    """Token type "enum"."""
    NONTIMED = 1
    TIMED = 2


SIGNERS = {
    TokenType.TIMED: itsdangerous.TimestampSigner,
    TokenType.NONTIMED: itsdangerous.Signer,
}


def _gen_fname(length) -> str:
    """Generate a random filename."""
    return ''.join(secrets.choice(ALPHABET)
                   for _ in range(length))


async def gen_filename(request, length=3) -> str:
    """Generate a random filename, without clashes.

    This has a limit of generating a 10 character filename.
    Any attempts to get more characters will result
    in a RuntimeError.
    """
    if length > 10:
        raise RuntimeError('Failed to generate a filename')

    for _ in range(10):
        # generate random, check against db
        # if exists, continue loop
        # if not, return
        random_fname = _gen_fname(length)

        filerow = await request.app.db.fetchrow("""
        SELECT file_id
        FROM files
        WHERE filename = $1
        """, random_fname)

        if not filerow:
            return random_fname

    # if 10 tries didnt work, try generating with length+1
    return await gen_filename(request, length + 1)
