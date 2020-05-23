CREATE TABLE IF NOT EXISTS datadump_queue (
    job_id uuid primary key,
    name text unique,

    state bigint default 0,
    errors text default '',
    inserted_at timestamp without time zone default (now() at time zone 'utc'),
    scheduled_at timestamp without time zone default (now() at time zone 'utc'),
    taken_at timestamp without time zone default null,
    internal_state jsonb default '{}',

    user_id bigint REFERENCES users (user_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS mass_delete_queue (
    job_id uuid primary key,
    name text unique,

    state bigint default 0,
    errors text default '',
    inserted_at timestamp without time zone default (now() at time zone 'utc'),
    scheduled_at timestamp without time zone default (now() at time zone 'utc'),
    taken_at timestamp without time zone default null,
    internal_state jsonb default '{}',

    user_id bigint REFERENCES users (user_id) ON DELETE CASCADE,
    query jsonb default '{}'
);
