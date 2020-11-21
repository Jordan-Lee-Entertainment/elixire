# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import logging

log = logging.getLogger(__name__)


async def file_total_counts(app):
    """Submit total file count."""
    total_files = await app.db.fetchval(
        """
        SELECT COUNT(*)
        FROM files
        """
    )

    total_files_public = await app.db.fetchval(
        """
        SELECT COUNT(*)
        FROM files
        JOIN user_settings ON files.uploader = user_settings.user_id
        WHERE user_settings.consented = true
        """
    )

    metrics = app.metrics
    await metrics.submit("total_files", total_files)
    await metrics.submit("total_files_public", total_files_public)


async def file_size_counts(app):
    """Submit file sizes in megabytes."""
    total_size = (
        await app.db.fetchval(
            """
    SELECT SUM(file_size) / 1048576
    FROM files
    """
        )
        or 0.0
    )

    total_size_public = (
        await app.db.fetchval(
            """
    SELECT SUM(file_size) / 1048576
    FROM files
    JOIN user_settings ON files.uploader = user_settings.user_id
    WHERE user_settings.consented = true
    """
        )
        or 0.0
    )

    metrics = app.metrics
    await metrics.submit("total_size", total_size)
    await metrics.submit("total_size_public", total_size_public)


async def user_counts(app):
    """Submit information related to our users."""
    active = await app.db.fetchval(
        """
        SELECT COUNT(*)
        FROM users
        WHERE active = true
        """
    )

    consented = await app.db.fetchval(
        """
        SELECT COUNT(*)
        FROM users
        JOIN user_settings ON user_settings.user_id = users.user_id
        WHERE active = true AND consented = true
        """
    )

    inactive = await app.db.fetchval(
        """
        SELECT COUNT(*)
        FROM users
        WHERE active = false
        """
    )

    metrics = app.metrics
    await metrics.submit("active_users", active)
    await metrics.submit("consented_users", consented)
    await metrics.submit("inactive_users", inactive)


async def upload_uniq_task(app):
    """Count the amount of unique uploaders in the past hour."""
    metrics = app.metrics

    count = await app.db.fetchval(
        """
        SELECT COUNT(DISTINCT uploader)
        FROM files
        WHERE file_id > time_snowflake(now() - interval '1 hour')
        """
    )

    await metrics.submit("unique_uploaders_hour", count)

    countpub = await app.db.fetchval(
        """
        SELECT COUNT(DISTINCT uploader)
        FROM files
        JOIN user_settings ON files.uploader = user_settings.user_id
        WHERE file_id > time_snowflake(now() - interval '1 hour')
            AND user_settings.consented = true
        """
    )

    await metrics.submit("unique_uploaders_hour_pub", countpub)


async def hourly_tasks(app):
    """Functions to be run hourly."""
    await file_total_counts(app)
    await file_size_counts(app)
    await user_counts(app)
    await upload_uniq_task(app)
