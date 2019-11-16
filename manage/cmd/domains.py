# elixire: Image Host software
# Copyright 2018-2019, elixi.re Team and the elixire contributors
# SPDX-License-Identifier: AGPL-3.0-only

from api.common.domain import create_domain_tag, delete_domain_tag


async def create_tag(_ctx, args):
    tag_id = await create_domain_tag(args.label)
    print("created tag with id", tag_id)


async def delete_tag(_ctx, args):
    await delete_domain_tag(args.tag_id)
    print("OK")


def setup(subparser):
    parser_create_tag = subparser.add_parser("create_tag", help="Create a domain tag",)
    parser_create_tag.add_argument("label")
    parser_create_tag.set_defaults(func=create_tag)

    parser_delete_tag = subparser.add_parser("delete_tag", help="Delete a domain tag",)
    parser_delete_tag.add_argument("tag_id")
    parser_delete_tag.set_defaults(func=delete_tag)
