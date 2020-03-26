# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

"""
elixire db migration script.
"""
import importlib
import logging

from pathlib import Path
from inspect import stack
from collections import namedtuple
from enum import Enum

from quart import current_app as app

import asyncpg

log = logging.getLogger(__name__)


class ScriptType(Enum):
    SQL = 0
    Python = 1


Migration = namedtuple("Migration", "mid name path type")


def _get_mig_folder() -> Path:
    """Fetch a Path instance for the
    folder holding the migration SQL scripts."""
    # first, we need this file's path
    # via inspect.stack()
    cmd_path = stack()[0][1]

    # extract one level up (the folder)
    cmd_folder = Path("/".join(cmd_path.split("/")[:-1]))

    # then we'll have the migration folder
    return cmd_folder / "scripts"


class MigrationContext:
    """Migration context class.

    Contains the list of current SQL scripts on the
    manage/cmd/migration/scripts folder.
    """

    def __init__(self):
        self.migration_folder = _get_mig_folder()
        self.scripts = self._get_scripts()

    def _get_scripts(self):
        mig_folder = self.migration_folder
        migrations = {}

        for migration_path in mig_folder.iterdir():
            if migration_path.name.startswith(".") or migration_path.name.startswith(
                "_"
            ):
                continue

            is_sql = migration_path.name.endswith(".sql")
            is_python = migration_path.name.endswith(".py")
            if not is_sql and not is_python:
                continue

            # we need to extract the migration's
            # ID and name to insert in the dictionary
            filename = migration_path.name

            # a migration filename is composed of:
            # <ID>_<migration's name>.sql
            # example:
            # 6_add_users_index.sql
            fragments = filename.split("_")

            mig_id = int(fragments[0])
            mig_name = "_".join(fragments[1:])

            migrations[mig_id] = Migration(
                mig_id,
                mig_name,
                migration_path,
                ScriptType.SQL if is_sql else ScriptType.Python,
            )

        return migrations

    @property
    def latest(self):
        """Give the latest Migration ID."""

        # if there are no scripts in the table, return
        # latest as 0 (migrations start from 1).
        if not self.scripts:
            return 0

        return max(self.scripts.keys())


async def _ensure_changelog(mctx) -> int:
    """Ensure a migration log exists
    in the database."""
    try:
        await app.db.execute(
            """
        CREATE TABLE migration_log (
            change_id bigint PRIMARY KEY,

            apply_ts timestamp without time zone default
                (now() at time zone 'utc'),

            description text
        )
        """
        )

        # if we are just creating the table,
        # then we'll assume the current database is
        # in latest schema.sql.
        await app.db.execute(
            """
        INSERT INTO migration_log
            (change_id, description)
        VALUES
            ($1, $2)
        """,
            mctx.latest,
            "migration table setup",
        )

        log.debug("migration table created")
    except asyncpg.DuplicateTableError:
        log.debug("existing migration log")

    return (
        await app.db.fetchval(
            """
    SELECT MAX(change_id)
    FROM migration_log
    """
        )
        or 0
    )


async def _apply_sql(migration):
    # get this migration's raw sql to apply
    raw_sql = migration.path.read_text(encoding="utf-8")
    await app.db.execute(raw_sql)


async def _apply_py(migration):
    module = importlib.import_module(
        "manage.cmd.migration.scripts." + migration.path.name.replace(".py", "")
    )
    await module.run(app)


async def apply_migration(migration: Migration):
    """Apply a single migration to the database."""

    # check if we already applied
    apply_ts = await app.db.fetchval(
        """
    SELECT apply_ts
    FROM migration_log
    WHERE change_id = $1
    """,
        migration.mid,
    )

    if apply_ts is not None:
        print("already applied", migration.mid, ": skipping")
        return

    try:
        if migration.type == ScriptType.SQL:
            await _apply_sql(migration)
        elif migration.type == ScriptType.Python:
            await _apply_py(migration)

        await app.db.execute(
            """
            INSERT INTO migration_log
                (change_id, description)
            VALUES
                ($1, $2)
            """,
            migration.mid,
            f"migration: {migration.name}",
        )

        print("applied", migration.mid, migration.name)
    except Exception:
        # do not let the error make this an applied migration
        # in the logs.
        log.exception("error while applying migration")


async def migrate_cmd(_args):
    """Migration command."""

    mctx = MigrationContext()

    # make sure we have the migration_log
    # table created, as it is required for
    # proper checking of the current database's
    # version (relative to schema.sql)

    # it returns the current database's local
    # latest change id, so we can compare
    # this value against MigrationContext.latest.
    local_latest = await _ensure_changelog(mctx)

    log.debug("%d migrations loaded", len(mctx.scripts))

    print("local", local_latest, "latest", mctx.latest)

    if local_latest == mctx.latest:
        print("local == latest, no changes to do")
        return

    # sanity check
    if local_latest > mctx.latest:
        print("local > latest, this is impossible. " "please fix database manually")
        return

    # if we are outdated from latest
    # (which is the normal case)
    # we iterate over
    # [local_latest + 1, ..., mctx.latest] (inclusive)
    # applying every migration ID in that range.
    for mig_id in range(local_latest + 1, mctx.latest + 1):
        migration = mctx.scripts.get(mig_id)

        if not migration:
            print("skipping migration", mig_id, "not found")
            continue

        await apply_migration(migration)

    print("OK")


def setup(subparsers):
    """Setup migration command."""
    parser_migrate = subparsers.add_parser("migrate", help="Migrate the database")

    parser_migrate.set_defaults(func=migrate_cmd)
