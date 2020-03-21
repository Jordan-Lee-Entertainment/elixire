# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

from typing import Optional, Dict, Any
from quart import current_app as app
from api.storage import object_key


class Shorten:
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

        # TODO set redirto to empty string?
        await app.db.fetchrow(
            f"""
            UPDATE shortens
            SET deleted = true
            WHERE shorten_id = $1
              AND deleted = false
            """,
            self.id,
        )

        await app.storage.raw_invalidate(
            object_key("redir", self.domain_id, self.subdomain, self.shortname)
        )
