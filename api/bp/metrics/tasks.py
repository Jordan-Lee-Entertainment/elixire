# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import logging
import asyncio


log = logging.getLogger(__name__)


async def second_tasks(app):
    """Quick submission of per-second metrics."""
    metrics = app.metrics
    counters = app.counters

    for counter, counter_val in counters.data.items():
        # ignore those specific counters, as they're on their own task
        if counter in ('file_upload_hour', 'file_upload_hour_pub'):
            continue

        await metrics.submit(counter, counter_val)
        counters.reset_single(counter)


async def file_upload_counts(app):
    """Submit the counters for total amount of uploads."""
    metrics = app.metrics
    counters = app.counters

    await counters.auto_submit(metrics, 'file_upload_hour')
    await counters.auto_submit(metrics, 'file_upload_hour_pub')


async def file_total_counts(app):
    """Submit total file count."""
    total_files = await app.db.fetchval("""
    SELECT COUNT(*)
    FROM files
    """)

    total_files_public = await app.db.fetchval("""
    SELECT COUNT(*)
    FROM files
    JOIN users on files.uploader = users.user_id
    WHERE users.consented = true
    """)

    metrics = app.metrics
    await metrics.submit('total_files', total_files)
    await metrics.submit('total_files_public', total_files_public)


async def file_size_counts(app):
    """Submit file sizes in megabytes."""
    total_size = await app.db.fetchval("""
    SELECT SUM(file_size) / 1048576
    FROM files
    """) or 0.0

    total_size_public = await app.db.fetchval("""
    SELECT SUM(file_size) / 1048576
    FROM files
    JOIN users ON files.uploader = users.user_id
    WHERE users.consented = true
    """) or 0.0

    metrics = app.metrics
    await metrics.submit('total_size', total_size)
    await metrics.submit('total_size_public', total_size_public)


async def user_counts(app):
    """Submit information related to our users."""
    active = await app.db.fetchval("""
    SELECT COUNT(*)
    FROM users
    WHERE active = true
    """)

    consented = await app.db.fetchval("""
    SELECT COUNT(*)
    FROM users
    WHERE active = true AND consented = true
    """)

    inactive = await app.db.fetchval("""
    SELECT COUNT(*)
    FROM users
    WHERE active = false
    """)

    metrics = app.metrics
    await metrics.submit('active_users', active)
    await metrics.submit('consented_users', consented)
    await metrics.submit('inactive_users', inactive)


async def hourly_tasks(app):
    """Functions to be run hourly."""
    await file_upload_counts(app)
    await file_total_counts(app)
    await file_size_counts(app)
    await user_counts(app)


async def upload_uniq_task(app):
    """Count the amount of unique uploads and uploaders
    in the past 24 hours."""
    metrics = app.metrics

    count = await app.db.fetchval("""
    SELECT COUNT(DISTINCT uploader)
    FROM files
    WHERE file_id > time_snowflake(now() - interval '24 hours')
    """)

    await metrics.submit('uniq_uploaders_day', count)

    countpub = await app.db.fetchval("""
    SELECT COUNT(DISTINCT uploader)
    FROM files
    JOIN users ON users.user_id = files.uploader
    WHERE file_id > time_snowflake(now() - interval '24 hours')
        AND users.consented = true
    """)

    await metrics.submit('uniq_uploaders_day_pub', countpub)

    await asyncio.sleep(86400)
