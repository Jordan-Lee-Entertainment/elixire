from asyncpg import UniqueViolationError


async def _add(ctx, drow, field, target):
    domain_id = drow["domain_id"]

    if not drow[field]:
        print("ignored domain", domain_id, field, "not set")
        return

    try:
        await ctx.db.execute(
            f"""INSERT INTO domain_tags(domain_id, tag_id) VALUES ($1, {target})""",
            domain_id,
        )
        print("add tag for", domain_id, field)
    except UniqueViolationError:
        print("ignored domain", domain_id, field, "tag already in")


async def run(ctx):
    # admin_only is tag 1
    # official is tag 2

    domains = await ctx.db.fetch(
        """
        SELECT domain_id, admin_only, official
        FROM domains
        """
    )

    print("processing", len(domains), "domains")

    for drow in domains:
        await _add(ctx, drow, "admin_only", 1)
        await _add(ctx, drow, "official", 2)
