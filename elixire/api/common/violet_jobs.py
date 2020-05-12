from typing import List
from asyncpg import Record


def violet_jobs_to_json(jobs: List[Record]) -> List[dict]:
    return [
        {
            **dict(r),
            **{
                "job_id": r["job_id"].hex,
                "inserted_at": r["inserted_at"].isoformat(),
                "taken_at": r["taken_at"].isoformat()
                if r["taken_at"] is not None
                else None,
            },
        }
        for r in jobs
    ]
