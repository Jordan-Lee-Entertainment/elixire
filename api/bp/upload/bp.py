# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import logging
import pathlib
import time
from datetime import datetime
from typing import Any, Dict, Optional

import metomi.isodatetime.parsers as parse
from quart import Blueprint, jsonify, current_app as app, request
from hail import Flake
from winter import get_snowflake
from dateutil.relativedelta import relativedelta

from api.storage import object_key
from api.enums import FileNameType
from api.common import transform_wildcard
from api.common.auth import check_admin, token_check
from api.common.utils import resolve_domain
from api.common.profile import gen_user_shortname
from api.models import User
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


def _to_relativedelta(duration) -> relativedelta:
    """
    Convert metomi's Duration object into a dateutil's relativedelta object.
    """
    fields = ("years", "months", "weeks", "days", "hours", "minutes", "seconds")

    # I'm not supposed to pass None to relativedelta or else it oofs
    kwargs = {}
    for field in fields:
        value = getattr(duration, field)
        if value is not None:
            kwargs[field] = value

    return relativedelta(**kwargs)


async def _maybe_schedule_deletion(ctx: UploadContext) -> Optional[Flake]:
    duration_str: Optional[str] = request.args.get("file_duration")
    if duration_str is None:
        return None

    duration = parse.DurationParser().parse(duration_str)
    now = datetime.utcnow()
    relative_delta = _to_relativedelta(duration)
    scheduled_at = now + relative_delta

    job_id = await app.sched.push_queue(
        "scheduled_deletes", ["file", ctx.file_id], scheduled_at=scheduled_at
    )
    return job_id


def _check_duration():
    duration_str = request.args.get("duration")
    if duration_str is not None:
        _ = parse.DurationParser().parse(duration_str)
        # TODO: check if negative


@bp.route("/upload", methods=["POST"])
async def upload_handler():
    """Main upload handler."""
    user_id = await token_check()
    user = await User.fetch(user_id)
    assert user is not None

    _check_duration()

    # if admin is set on request.args, we will # do an "admin upload", without
    # any checking for viruses, weekly limits, MIME, etc.
    do_checks = not bool(request.args.get("admin"))

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

    domain_id, domain, subdomain_name = await resolve_domain(user_id, FileNameType.FILE)

    # upload counter
    app.counters.inc("file_upload_hour")

    # TODO maybe push this to a background task
    if user.settings.consented:
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

    await _maybe_schedule_deletion(ctx)

    await upload_metrics(ctx)
    return jsonify(
        {"url": _construct_url(domain, shortname, extension), "shortname": shortname}
    )
