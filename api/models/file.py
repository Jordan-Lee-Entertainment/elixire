# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

import os.path
from typing import Optional, Dict, Any, List
from quart import current_app as app


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


class File:
    """File model."""

    def __init__(self, row):
        self.id: int = row["file_id"]
        self.mimetype: str = row["mimetype"]
        self.shortname: str = row["filename"]
        self.file_size: int = row["file_size"]
        self.uploader: int = row["uploader"]
        self.fspath: str = row["fspath"]
        self.deleted: bool = row["deleted"]
        self.domain_id: int = row["domain"]
        self.subdomain: Optional[str] = row["subdomain"]

    @classmethod
    async def fetch(cls, file_id: int) -> "File":
        row = await app.db.fetchrow(
            """
            SELECT file_id, mimetype, filename, file_size, uploader, fspath,
                   deleted, domain, subdomain
            FROM files
            WHERE file_id = $1
            """,
            file_id,
        )

        return cls(row)

    def to_dict(self, *, public: bool = False) -> Dict[str, Any]:
        file_dict = {
            "id": self.id,
            "mimetype": self.mimetype,
            "shortname": self.shortname,
            "size": self.file_size,
            "uploader": self.uploader,
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
