# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import logging
import pathlib
import time
from typing import Any, Dict, Optional, Tuple

from quart import Blueprint, jsonify, current_app as app, request

from api.common import get_domain_info, transform_wildcard
from api.common.auth import check_admin, gen_shortname, token_check
from api.permissions import Permissions, domain_permissions
from api.snowflake import get_snowflake
from .context import UploadContext
from .file import UploadFile

# TODO move to api.common
from ..metrics import is_consenting

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
        SELECT filename, domain
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

    # NOTE files.subdomain doesn't exist (see issue 44)
    domain = transform_wildcard(domain, "i")

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


def _fetch_domain() -> Tuple[Optional[int], Optional[str]]:
    """Fetch domain information, if any"""
    try:
        given_domain: Optional[int] = int(request.args["domain"])
    except (KeyError, ValueError):
        given_domain = None

    try:
        given_subdomain = request.args["subdomain"]
    except KeyError:
        given_subdomain = None

    return given_domain, given_subdomain


@bp.route("/upload", methods=["POST"])
async def upload_handler():
    """Main upload handler."""
    user_id = await token_check()

    # if admin is set on request.args, we will # do an "admin upload", without
    # any checking for viruses, weekly limits, MIME, etc.
    do_checks = not bool(request.args.get("admin"))
    given_domain, given_subdomain = _fetch_domain()

    # if the user is admin and they wanted an admin
    # upload, check if they're actually an admin
    if not do_checks:
        await check_admin(user_id, True)

    # TODO cleaner api with request contextvar
    file = await UploadFile.from_request()

    # by default, assume the extension given in the filename
    # is the one we should use.
    #
    # this will be true if the upload is an admin upload, but if it isn't
    # we need to check MIMEs to ensure a proper extension is used for security
    extension = file.given_extension

    # generate a filename so we can identify later when removing it
    # because of virus scanning.
    shortname, tries = await gen_shortname(user_id)
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

    # perform any checks like virus scanning and quota limits. this method will
    # also check the MIME type, and return the extension that we should be
    # using. (admins get to bypass!)
    if do_checks:
        extension = await ctx.perform_checks(app)

    await ctx.file.resolve(extension)

    # we search for the file path's existance before finding any repeated file
    # since in an *ideal* scenario this doesn't happen and we'd rather decrease
    # the amount of db calls we do in the ideal code path
    if file.path.exists():
        repeat = await find_repeat(ctx, extension)
        if repeat is not None:
            await upload_metrics(ctx)
            return jsonify(repeat)

    user_domain_id, user_subdomain, user_domain = await get_domain_info(user_id)
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
    if await is_consenting(user_id):
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
            file_size, uploader, fspath, domain
        )
        VALUES ($1, $2, $3, $4, $5, $6, $7)
        """,
        file_id,
        ctx.file.mime,
        shortname,
        file_size,
        user_id,
        file.raw_path,
        domain_id,
    )

    # TODO UploadFile.cache_key property
    await app.storage.raw_invalidate(f"fspath:{domain_id}:{shortname}")

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

    # upload file latency metrics
    await upload_metrics(ctx)

    instance_url = app.econfig.MAIN_URL

    return jsonify(
        {
            "url": _construct_url(domain, shortname, extension),
            "shortname": shortname,
            "delete_url": f"{instance_url}/api/files/{shortname}/delete",
        }
    )
