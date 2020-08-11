async def _migrate_admin_only(record, *, ctx, admin_only_tag_id) -> None:
    domain = record["domain"]
    domain_id = record["domain_id"]

    # Remove the `admin_only` tag.
    result = await ctx.db.execute(
        """
        DELETE FROM domain_tag_mappings
        WHERE domain_id = $1 AND tag_id = $2
        """,
        domain_id,
        admin_only_tag_id,
    )

    print(f"Deletion result: {result}")

    if result != "DELETE 1":
        print(f"Skipping {domain} ({domain_id}), doesn't have `admin_only` tag.")
        return

    await ctx.db.execute(
        """
        UPDATE domains
        SET admin_only = TRUE
        WHERE domain_id = $1
        """,
        domain_id,
    )

    print(f"Made {domain} ({domain_id}) `admin_only`.")


async def run(ctx) -> None:
    # Add the `admin_only` column back.
    print("Adding `admin_only` column.")
    await ctx.db.execute(
        """
        ALTER TABLE domains
        ADD COLUMN admin_only BOOLEAN DEFAULT FALSE NOT NULL;
        """
    )

    admin_only_tag_id = await ctx.db.fetchval(
        """
        SELECT tag_id
        FROM domain_tags
        WHERE label = 'admin_only'
        """
    )

    print(f"Former `admin_only` tag ID: {admin_only_tag_id}")

    if not admin_only_tag_id:
        raise RuntimeError("Unable to find the `admin_only` tag in `domain_tags`.")

    async with ctx.db.acquire() as conn:
        async with conn.transaction():
            async for record in conn.cursor("SELECT domain_id, domain FROM domains"):
                await _migrate_admin_only(
                    record, ctx=ctx, admin_only_tag_id=admin_only_tag_id
                )
