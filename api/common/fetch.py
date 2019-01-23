# elixire: Image Host software
# Copyright 2018, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

async def get_file_id(conn, file_name):
    """Get a file ID, given a file shortname."""
    return await conn.fetchval("""
    SELECT file_id
    FROM files
    WHERE filename = $1
    """, file_name)


async def get_shorten_id(conn, shorten_name):
    """Get a shorten ID, given a shorten shortname."""
    return await conn.fetchval("""
    SELECT shorten_id
    FROM shortens
    WHERE filename = $1
    """, shorten_name)


async def get_file(conn, file_id: int) -> dict:
    """Get a dictionary holding file information."""
    row = await conn.fetchrow("""
    SELECT file_id, mimetype, filename, file_size,
           uploader, fspath, deleted, domain
    FROM files
    WHERE file_id = $1
    """, file_id)

    if row is None:
        return None

    drow = dict(row)
    drow['file_id'] = str(drow['file_id'])
    drow['uploader'] = str(drow['uploader'])

    return drow


async def get_shorten(conn, shorten_id: int) -> dict:
    """Get a dictionary holding shorten information."""

    # NOTE: this is really a copypaste from get_file.
    # the old function was unified, called generic_namefetch,
    # it was shitty... so i split it into two.

    row = await conn.fetchrow("""
    SELECT shorten_id, filename, redirto, uploader,
           deleted, domain
    FROM shortens
    WHERE shorten_id = $1
    """, shorten_id)

    if row is None:
        return None

    drow = dict(row)
    drow['shorten_id'] = str(drow['shorten_id'])
    drow['uploader'] = str(drow['uploader'])

    return drow


OBJ_MAPPING = {
    'file': (get_file_id, get_file),
    'shorten': (get_shorten_id, get_shorten),
}
