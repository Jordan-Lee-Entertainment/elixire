# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import os.path
import logging
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any, List, Set, Awaitable
from quart import current_app as app
from hail import Flake

from api.models.resource import Resource
from api.storage import object_key
from api.errors import NotFound

log = logging.getLogger(__name__)


async def domain_list():
    """Returns a dictionary with domain IDs mapped to domain names"""
    return dict(
        await app.db.fetch(
            """
            SELECT domain_id, domain
            FROM domains
            """
        )
    )


def construct_domain(domains: Dict[int, str], elixire_file: "File") -> str:
    """Construct a full domain, given the list of domains and the object to
    put subdomains on. the default is "wildcard"."""
    domain = domains[elixire_file.domain_id]

    if domain.startswith("*."):
        domain = domain.replace("*", elixire_file.subdomain or "wildcard")

    return domain


def construct_url(domain: str, url_basename: str, *, scope: str = "i") -> str:
    """Create an URL for the given basename."""

    # http is allowed for local testing
    prefix = "https://" if app.econfig.USE_HTTPS else "http://"
    return f"{prefix}{domain}/{scope}/{url_basename}"


class File(Resource):
    """File model."""

    __slots__ = (
        "id",
        "mimetype",
        "shortname",
        "file_size",
        "uploader_id",
        "fspath",
        "deleted",
        "domain_id",
        "subdomain",
    )

    def __init__(self, row):
        self.id: int = row["file_id"]
        self.mimetype: str = row["mimetype"]
        self.shortname: str = row["filename"]
        self.file_size: int = row["file_size"]
        self.uploader_id: int = row["uploader"]
        self.fspath: str = row["fspath"]
        self.deleted: bool = row["deleted"]
        self.domain_id: int = row["domain"]
        self.subdomain: Optional[str] = row["subdomain"]

    @classmethod
    async def fetch(cls, file_id: int) -> Optional["File"]:
        row = await app.db.fetchrow(
            """
            SELECT file_id, mimetype, filename, file_size, uploader, fspath,
                   deleted, domain, subdomain
            FROM files
            WHERE file_id = $1
            """,
            file_id,
        )

        if row is None:
            return None

        return cls(row)

    @classmethod
    async def fetch_by(cls, *, shortname: str) -> Optional["File"]:
        row = await app.db.fetchrow(
            """
            SELECT file_id, mimetype, filename, file_size, uploader, fspath,
                   deleted, domain, subdomain
            FROM files
            WHERE filename = $1
            """,
            shortname,
        )

        if row is None:
            return None

        return cls(row)

    @classmethod
    async def fetch_by_with_uploader(
        cls,
        uploader_id: int,
        *,
        file_id: Optional[int] = None,
        shortname: Optional[str] = None,
    ) -> "File":
        """Fetch a file but only return it if the given uploader id
        matches with the file's uploader.

        Raises NotFound if the file isn't found or the uploader mismatches."""
        assert file_id or shortname
        if file_id:
            elixire_file = await cls.fetch(file_id)
        elif shortname:
            elixire_file = await cls.fetch_by(shortname=shortname)

        if elixire_file is None or elixire_file.uploader_id != uploader_id:
            raise NotFound("File not found")

        return elixire_file

    def to_dict(self, *, public: bool = False) -> Dict[str, Any]:
        file_dict = {
            "id": self.id,
            "mimetype": self.mimetype,
            "shortname": self.shortname,
            "size": self.file_size,
            "uploader": self.uploader_id,
            "fspath": self.fspath,
            "deleted": self.deleted,
            "domain": self.domain_id,
            "subdomain": self.subdomain,
        }

        if public:
            file_dict.pop("uploader")
            file_dict.pop("fspath")
            file_dict.pop("deleted")
            file_dict.pop("domain")
            file_dict.pop("subdomain")

        return file_dict

    @classmethod
    async def construct_urls(cls, files: List["File"]) -> List[Dict[str, str]]:
        urls = []

        domain_data = await domain_list()

        for elixire_file in files:
            domain = construct_domain(domain_data, elixire_file)

            # extract extension from the fspath's basename
            fspath_basename = os.path.basename(elixire_file.fspath)
            fspath_extension = fspath_basename.split(".")[-1]
            concatenated_url_basename = f"{elixire_file.shortname}.{fspath_extension}"

            url_dict = {"url": construct_url(domain, concatenated_url_basename)}

            if elixire_file.mimetype.startswith("image/"):
                url_dict["thumbnail"] = construct_url(
                    domain, f"s{elixire_file.shortname}", scope="t"
                )

            urls.append(url_dict)

        return urls

    async def _remove_fspath(self):
        # fetch all files with the same fspath
        # and on the hash system, means the same hash
        row = await app.db.fetchrow(
            """
            SELECT fspath, COUNT(*)
            FROM files
            WHERE fspath = (SELECT fspath FROM files WHERE file_id = $1)
              AND deleted = false
            GROUP BY fspath
            """,
            self.id,
        )

        if row is None:
            return

        fspath, same_fspath = row["fspath"], row["count"]

        if same_fspath != 0:
            log.info(
                "there are still %d files with the same fspath %r, not deleting",
                same_fspath,
                fspath,
            )
            return

        path = Path(fspath)
        try:
            path.unlink()
            log.info("Deleted %r since no files refer to it", fspath)
        except FileNotFoundError:
            log.warning("fspath %s does not exist", fspath)

    async def delete(self, *, full: bool = False):
        """Delete a file.

        Parameters
        ----------
        full, optional: bool
            Move the ownership of the file to the doll user.
        """

        if not full:
            await app.db.fetchrow(
                """
                UPDATE files
                SET deleted = true
                WHERE uploader = $1
                  AND file_id = $2
                AND deleted = false
                """,
                self.uploader_id,
                self.id,
            )
        else:
            await app.db.fetchrow(
                """
                UPDATE files
                SET uploader = 0,
                    file_size = 0,
                    fspath = '',
                    deleted = true,
                    domain = 0
                WHERE
                    file_id = $1
                """,
                self.id,
            )

        await self._remove_fspath()
        await app.storage.raw_invalidate(
            object_key("fspath", self.domain_id, self.subdomain, self.shortname)
        )

    @classmethod
    async def delete_file_user_lock(self, user_id: int, file_id: int) -> None:
        """Delete a file using the user's specific delete semaphore."""
        lock = app.locks["delete_files"][user_id]
        async with lock:
            elixire_file = await File.fetch(file_id)
            assert elixire_file is not None
            await elixire_file.delete(full=True)

    @classmethod
    async def delete_many(
        cls, file_ids: List[int], *, user_id: int, timeout: Optional[int] = None
    ) -> Set[Awaitable[Any]]:
        """Delete many files. Requires the user_id for locking.

        Returns a list of tasks that are still waiting to delete. If
        ``timeout`` is None, the returned list must be empty.
        """

        if not file_ids:
            return set()

        tasks = [
            app.sched.spawn(
                cls.delete_file_user_lock,
                [user_id, file_id],
                name=f"delete_file:{file_id}",
            )
            for file_id in file_ids
        ]

        log.info("waiting for %d file tasks", len(tasks))
        done, pending = await asyncio.wait(tasks, timeout=timeout)

        log.info(
            "waited for %d file tasks, %d done, %d pending",
            len(tasks),
            len(done),
            len(pending),
        )

        for task in done:
            try:
                task.result()
            except Exception:
                log.exception("exception while deleting file")

        if timeout is None:
            assert not pending

        # mypy kind of fucks up here. sorry.
        return pending

    async def schedule_deletion(self, user) -> Optional[Flake]:
        return await self._internal_schedule_deletion(user, file_id=self.id)
