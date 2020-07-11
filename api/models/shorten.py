# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

from typing import Optional, Dict, Any
from quart import current_app as app
from hail import Flake

from api.storage import object_key
from api.errors import NotFound
from api.models.resource import Resource


class Shorten(Resource):
    __slots__ = (
        "id",
        "shortname",
        "redirto",
        "uploader_id",
        "deleted",
        "domain_id",
        "subdomain",
    )

    def __init__(self, row):
        self.id: int = row["shorten_id"]
        self.shortname: str = row["filename"]
        self.redirto: str = row["redirto"]
        self.uploader_id: int = row["uploader"]
        self.deleted: bool = row["deleted"]
        self.domain_id: int = row["domain"]
        self.subdomain: str = row["subdomain"]

    @classmethod
    async def fetch(cls, shorten_id: int) -> Optional["Shorten"]:
        row = await app.db.fetchrow(
            """
            SELECT shorten_id, filename, redirto, uploader, deleted, domain, subdomain
            FROM shortens
            WHERE shorten_id = $1
            """,
            shorten_id,
        )

        if row is None:
            return None

        return Shorten(row)

    @classmethod
    async def fetch_by(cls, *, shortname: str) -> Optional["Shorten"]:
        row = await app.db.fetchrow(
            """
            SELECT shorten_id, filename, redirto, uploader, deleted, domain, subdomain
            FROM shortens
            WHERE shortname = $1
            """,
            shortname,
        )

        if row is None:
            return None

        return Shorten(row)

    @classmethod
    async def fetch_by_with_uploader(
        cls,
        uploader_id: int,
        *,
        shorten_id: Optional[int] = None,
        shortname: Optional[str] = None,
    ) -> "Shorten":
        """Fetch a shorten but only return it if the given uploader id
        matches with the shorten's uploader.

        Raises NotFound if the shorten isn't found or the uploader mismatches."""
        assert shorten_id or shortname
        if shorten_id:
            shorten = await cls.fetch(shorten_id)
        elif shortname:
            shorten = await cls.fetch_by(shortname=shortname)

        if shorten is None or shorten.uploader_id != uploader_id:
            raise NotFound("Shorten not found")

        return shorten

    def to_dict(self, *, public: bool = False) -> Dict[str, Any]:
        file_dict = {
            "id": self.id,
            "shortname": self.shortname,
            "uploader": self.uploader_id,
            "redirto": self.redirto,
            "deleted": self.deleted,
            "domain": self.domain_id,
            "subdomain": self.subdomain,
        }

        if public:
            file_dict.pop("uploader")
            file_dict.pop("deleted")
            file_dict.pop("domain")
            file_dict.pop("subdomain")

        return file_dict

    async def delete(self) -> None:
        """Delete the shorten."""

        await app.db.fetchrow(
            f"""
            UPDATE shortens
            SET deleted = true,
                redirto = ''
            WHERE shorten_id = $1
              AND deleted = false
            """,
            self.id,
        )

        await app.storage.raw_invalidate(
            object_key("redir", self.domain_id, self.subdomain, self.shortname)
        )

    async def schedule_deletion(self, user) -> Optional[Flake]:
        return await self._internal_schedule_deletion(user, shorten_id=self.id)
