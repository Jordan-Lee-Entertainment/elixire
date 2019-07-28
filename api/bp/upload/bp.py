# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import logging
import pathlib
import time
from typing import Any, Dict, Optional, Tuple

from quart import Blueprint, jsonify, current_app as app, request

from api.common import get_domain_info, get_random_domain, transform_wildcard
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


async def check_repeat(
    fspath: str, extension: str, ctx: UploadContext
) -> Optional[Dict[str, Any]]:
    # check which files have the same fspath (the same hash)
    files = await app.db.fetch(
        """
    SELECT filename, uploader, domain
    FROM files
    WHERE fspath = $1 AND files.deleted = false
    """,
        fspath,
    )

    # get the first file, if any, from the uploader
    try:
        ufile = next(frow for frow in files if frow["uploader"] == ctx.user_id)
    except StopIteration:
        # no files for the user were found.
        return

    # fetch domain info about that file
    domain = await app.db.fetchval(
        """
    SELECT domain
    FROM domains
    WHERE domain_id = $1
    """,
        ufile["domain"],
    )

    # use 'i' as subdomain by default
    # since files.subdomain isn't a thing.
    domain = transform_wildcard(domain, "i")

    return {
        "url": _construct_url(domain, ufile["filename"], extension),
        "repeated": True,
        "shortname": ufile["filename"],
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
        given_domain = int(request.args["domain"])
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
    random_domain = bool(request.args.get("random"))
    given_domain, given_subdomain = _fetch_domain()

    # if the user is admin and they wanted an admin
    # upload, check if they're actually an admin
    if not do_checks:
        await check_admin(user_id, True)

    # TODO cleaner api with request contextvar
    file = await UploadFile.from_request(request)

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

    # perform any checks like virus scanning and quota limits. this method will
    # also check the MIME type, and return the extension that we should be
    # using. (admins get to bypass!)
    if do_checks:
        extension = await ctx.perform_checks(app)

    # hash the file and give it a path on the filesystem
    # (this sets the path and hash attributes)
    await ctx.file.hash_file(app)
    await ctx.file.resolve(app, extension)

    # give the file an id
    file_id = get_snowflake()
    ctx.file.id = file_id

    # file already exists? let's just return the existing one
    if file.path.exists():
        res = await check_repeat(file.raw_path, extension, ctx)
        if res is not None:
            await upload_metrics(ctx)
            return jsonify(res)

    # at this point, we have to resolve the domain (and subdomain) that the file
    # will be placed on.
    #
    # however, this is quite complicated:
    # - the user can specify ?random=1 to pick a random domain
    # - the user can specify a specific domain or subdomain they want the file
    #   to be uploaded on for this request SPECIFICALLY
    # - if the user specifies a random domain, we need to use their specific
    #   subdomain or fallback on the account specified one
    #
    # we also want to fallback on the user's configured domain settings in their
    # account settings.

    # get the user's domain settings
    user_domain_id, user_subdomain, user_domain = await get_domain_info(user_id)

    if random_domain:
        # let's get a random domain and pretend that it was specified in the
        # request (given_subdomain is that)
        given_domain = await get_random_domain()
        domain_id = given_domain
        subdomain_name = given_subdomain
    else:
        # use the specified domain stuff from the request, but fall back
        # to the domain info
        domain_id = given_domain or user_domain_id
        subdomain_name = given_subdomain or user_subdomain

    # check if domain is uploadable
    await domain_permissions(app, domain_id, Permissions.UPLOAD)

    # if we don't have a domain yet, we need to resolve it:
    if given_domain is None:
        # no domain was specified in the request, let's just use the user's
        domain = user_domain
    else:
        # a specific domain was specified, fetch that one from database
        domain = await app.db.fetchval(
            """
        SELECT domain
        FROM domains
        WHERE domain_id = $1
        """,
            given_domain,
        )

    # the domain might have *. at the beginning, let's replace that with the
    # provided subdomain's name
    domain = transform_wildcard(domain, subdomain_name)

    # upload counter
    app.counters.inc("file_upload_hour")
    if await is_consenting(user_id):
        app.counters.inc("file_upload_hour_pub")

    # calculate the new file size, with the dupe decrease factor multiplied in
    # if necessary
    file_size = ctx.file.calculate_size(app.econfig.DUPE_DECREASE_FACTOR)

    # invalidating any existing file before
    await app.storage.raw_invalidate(f"fspath:{domain_id}:{shortname}")

    # insert into database
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

    # write to fs
    buffer = await ctx.strip_exif(app)
    with open(file.raw_path, "wb") as raw_file:
        raw_file.write(buffer.getvalue())

    # upload file latency metrics
    await upload_metrics(ctx)

    instance_url = app.econfig.MAIN_URL

    return jsonify(
        {
            "url": _construct_url(domain, shortname, extension),
            "shortname": shortname,
            "delete_url": f"{instance_url}/api/delete/{shortname}",
        }
    )
