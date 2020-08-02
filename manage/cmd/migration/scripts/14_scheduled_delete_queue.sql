CREATE TABLE IF NOT EXISTS scheduled_delete_queue (
    job_id uuid primary key,
    name text unique,

    state bigint default 0,
    errors text default '',
    inserted_at timestamp without time zone default (now() at time zone 'utc'),
    scheduled_at timestamp without time zone default (now() at time zone 'utc'),
    taken_at timestamp without time zone default null,
    internal_state jsonb default '{}',

    file_id bigint references files (file_id) default null,
    shorten_id bigint references shortens (shorten_id) default null
);
