from pathlib import Path


async def deletefiles(ctx, _args):
    """Clean files marked as deleted on the db."""
    to_delete = await ctx.db.fetch("""
    SELECT fspath
    FROM files
    WHERE files.deleted = true
    """)

    print(f'deleting {len(to_delete)} files')
    completed = 0

    for row in to_delete:
        fspath = row['fspath']
        path = Path(fspath)
        try:
            path.unlink()
            completed += 1
        except FileNotFoundError:
            print(f'fspath {fspath!r} not found')

    print(f"""
    out of {len(to_delete)} files to be deleted
    {completed} were actually deleted
    """)


async def rename_file(ctx, args):
    """Rename a file."""
    shortname = args.shortname
    renamed = args.renamed

    domain = await ctx.db.fetchval("""
    SELECT domain
    FROM files
    WHERE filename = $1 AND deleted = false
    """, shortname)

    if domain is None:
        return print(f'no files found with shortname {shortname!r}')

    existing_id = await ctx.db.fetchval("""
    SELECT file_id
    FROM files
    WHERE filename = $1
    """, renamed)

    if existing_id:
        return print(f'file {renamed} already exists, stopping!')

    exec_out = await ctx.db.execute("""
    UPDATE files
    SET filename = $1
    WHERE filename = $2
    AND deleted = false
    """, renamed, shortname)

    # invalidate etc
    await ctx.redis.delete(f'fspath:{domain}:{shortname}')
    await ctx.redis.delete(f'fspath:{domain}:{renamed}')

    print(f'SQL out: {exec_out}')


def setup(subparsers):
    parser_cleanup = subparsers.add_parser(
        'cleanup_files',
        help='Delete files from the image folder',
        description="""
Delete all files that are marked as deleted in the image directory.
This is a legacy operation for instances that did not update
to a version of the backend that deletes files.
        """
    )
    parser_cleanup.set_defaults(func=deletefiles)

    parser_rename = subparsers.add_parser(
        'rename_file',
        help='Rename a single file'
    )

    parser_rename.add_argument('shortname', help='old shortname for the file')
    parser_rename.add_argument('renamed', help='new shortname for the file')
    parser_rename.set_defaults(func=rename_file)
