from quart import current_app as app


async def fetch_autodelete_jobs(
    user_id: int, *, page: int, resource_type: str
) -> List[dict]:
    return await app.db.fetch(
        f"""
        SELECT job_id
        FROM violet_jobs
        WHERE queue = 'scheduled_deletes'
          AND args->>0 = $1
        """,
        resource_type,
    )
