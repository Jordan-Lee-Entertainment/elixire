# elixire: Image Host software
# Copyright 2018-2020, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

from api.common.domain import create_domain_tag, delete_domain_tag
from api.models import Domain


async def create_tag(_ctx, args):
    tag_id = await create_domain_tag(args.label)
    print("created tag with id", tag_id)


async def delete_tag(_ctx, args):
    await delete_domain_tag(args.tag_id)
    print("OK")


async def add_tag(_ctx, args):
    domain = await Domain.fetch(args.domain_id)
    assert domain is not None
    await domain.add_tag(args.tag_id)
    print("OK")


async def remove_tag(_ctx, args):
    domain = await Domain.fetch(args.domain_id)
    assert domain is not None
    await domain.remove_domain_tag(args.tag_id)
    print("OK")


async def list_domains(ctx, _args):
    domains = await ctx.db.fetch(
        """
        SELECT domain_id, domain
        FROM domains
        """
    )

    for domain in domains:
        domain_id = domain["domain_id"]
        print("id:", domain_id, "name:", domain["domain"])

        domain = await Domain.fetch(domain_id)
        assert domain is not None

        for tag in domain.tags:
            print("\ttag", tag.id, "label", tag.label)


def setup(subparser):
    parser_create_tag = subparser.add_parser("create_tag", help="Create a domain tag")
    parser_create_tag.add_argument("label")
    parser_create_tag.set_defaults(func=create_tag)

    parser_delete_tag = subparser.add_parser("delete_tag", help="Delete a domain tag")
    parser_delete_tag.add_argument("tag_id", type=int)
    parser_delete_tag.set_defaults(func=delete_tag)

    parser_delete_tag = subparser.add_parser(
        "add_tag", help="Add a domain tag to a domain"
    )
    parser_delete_tag.add_argument("domain_id", type=int)
    parser_delete_tag.add_argument("tag_id", type=int)
    parser_delete_tag.set_defaults(func=add_tag)

    parser_delete_tag = subparser.add_parser(
        "remove_tag",
        help="Remove a domain tag to a domain",
        description="If the tag isn't in the domain, this still says OK",
    )
    parser_delete_tag.add_argument("domain_id", type=int)
    parser_delete_tag.add_argument("tag_id", type=int)
    parser_delete_tag.set_defaults(func=remove_tag)

    parser_list_domains = subparser.add_parser(
        "list_domains", help="List domains in the instance"
    )
    parser_list_domains.set_defaults(func=list_domains)
