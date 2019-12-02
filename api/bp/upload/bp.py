# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import logging
import pathlib
import time
from typing import Any, Dict, Optional

from quart import Blueprint, jsonify, current_app as app, request

from api.storage import object_key
from api.common import get_user_domain_info, transform_wildcard
from api.common.auth import check_admin, token_check
from api.common.utils import get_domain_querystring
from api.permissions import Permissions, domain_permissions
from api.snowflake import get_snowflake
from api.common.profile import gen_user_shortname, is_metrics_consenting
from .context import UploadContext
from .file import UploadFile

bp = Blueprint("upload", __name__)
log = logging.getLogger(__name__)


def _construct_url(domain, shortname, extension):
    dpath = pathlib.Path(domain)
    final_path = dpath / "i" / f"{shortname}{extension}"

    return f"https://{final_path!s}"


async def find_repeat(ctx: UploadContext, extension: str) -> Optional[Dict[str, Any]]:
    """Find if there are any existing files with the same hash AND that were
    uploaded by the uploader of the current file."""
    repeat = await app.db.fetchrow(
        """
        SELECT filename, domain, subdomain
        FROM files
        WHERE fspath = $1 AND uploader = $2 AND files.deleted = false
        """,
        ctx.file.raw_path,
        ctx.user_id,
    )

    if repeat is None:
        return None

    # fetch domain info about that file
    domain = await app.db.fetchval(
        """
        SELECT domain
        FROM domains
        WHERE domain_id = $1
        """,
        repeat["domain"],
    )

    if domain is None:
        raise AssertionError(
            f'file.domain ({repeat["domain"]}) refers to unknown domain'
        )

    # if subdomain is:
    #  - None: use "i" as subdomain (v2/legacy file)
    #  - an empty string: use "" as subdomain, only accessible at root
    #  - a non-empty string: use it as subdomain

    subdomain = "i" if repeat["subdomain"] is None else repeat["subdomain"]
    domain = transform_wildcard(domain, subdomain)

    return {
        "repeated": True,
        "url": _construct_url(domain, repeat["filename"], extension),
        "shortname": repeat["filename"],
    }


async def upload_metrics(ctx):
    """Upload total time taken for procesisng to InfluxDB."""
    end = time.monotonic()
    metrics = app.metrics
    delta = round((end - ctx.start_timestamp) * 1000, 5)

    await metrics.submit("upload_latency", delta)


@bp.route("/upload", methods=["POST"])
async def upload_handler():
    """Main upload handler."""
    user_id = await token_check()

    # if admin is set on request.args, we will # do an "admin upload", without
    # any checking for viruses, weekly limits, MIME, etc.
    do_checks = not bool(request.args.get("admin"))
    given_domain, given_subdomain = get_domain_querystring()

    # if the user is admin and they wanted an admin
    # upload, check if they're actually an admin
    if not do_checks:
        await check_admin(user_id, True)

    file = await UploadFile.from_request()

    # generate a filename so we can identify later when removing it
    # because of virus scanning.
    shortname, tries = await gen_user_shortname(user_id)
    await app.metrics.submit("shortname_gen_tries", tries)

    # construct an upload context, which holds the file and other data about
    # the current upload
    ctx = UploadContext(
        file=file,
        user_id=user_id,
        shortname=shortname,
        do_checks=do_checks,
        start_timestamp=time.monotonic(),
    )

    file_id = get_snowflake()
    ctx.file.id = file_id

    mime, extension = await ctx.resolve_mime()

    # perform any checks like virus scanning and quota limits.
    await ctx.perform_checks()

    await ctx.file.resolve(extension)

    # we search for the file path's existance before finding any repeated file
    # since in an *ideal* scenario this doesn't happen and we'd rather decrease
    # the amount of db calls we do in the ideal code path
    if file.path.exists():
        repeat = await find_repeat(ctx, extension)
        if repeat is not None:
            await upload_metrics(ctx)
            return jsonify(repeat)

    user_domain_id, user_subdomain, user_domain = await get_user_domain_info(user_id)
    domain_id = given_domain or user_domain_id
    subdomain_name = given_subdomain or user_subdomain

    # check if domain is uploadable
    await domain_permissions(app, domain_id, Permissions.UPLOAD)

    # resolve the given (domain_id, subdomain_name) into a string
    if given_domain is None:
        domain = user_domain
    else:
        domain = await app.db.fetchval(
            """
            SELECT domain
            FROM domains
            WHERE domain_id = $1
            """,
            given_domain,
        )

    domain = transform_wildcard(domain, subdomain_name)

    # upload counter
    app.counters.inc("file_upload_hour")

    # TODO maybe push this to a background task
    if await is_metrics_consenting(user_id):
        app.counters.inc("file_upload_hour_pub")

    # calculate the new file size, with the dupe decrease factor multiplied in
    # if necessary
    file_size = ctx.file.calculate_size(app.econfig.DUPE_DECREASE_FACTOR)

    # insert into database
    # TODO a way to remove it from database if anything fails
    await app.db.execute(
        """
        INSERT INTO files (
            file_id, mimetype, filename,
            file_size, uploader, fspath, domain, subdomain
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        """,
        file_id,
        mime,
        shortname,
        file_size,
        user_id,
        file.raw_path,
        domain_id,
        subdomain_name,
    )

    await app.storage.set_with_ttl(
        object_key("fspath", domain_id, subdomain_name, shortname), file.raw_path, 600
    )

    # write the file to filesystem
    stream = await ctx.strip_exif()
    with open(file.raw_path, "wb") as output:

        # instead of copying the entire stream and writing
        # we copy ~128kb chunks to decrease total memory usage
        while True:
            chunk = stream.read(128 * 1024)
            if not chunk:
                break

            output.write(chunk)

    await upload_metrics(ctx)
    return jsonify(
        {"url": _construct_url(domain, shortname, extension), "shortname": shortname}
    )
