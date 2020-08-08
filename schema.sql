-- Thank you FrostLuma for giving those functions
-- convert Discord snowflake to timestamp
CREATE OR REPLACE FUNCTION snowflake_time (snowflake BIGINT)
    RETURNS TIMESTAMP AS $$
BEGIN
    RETURN to_timestamp(((snowflake >> 22) + 1420070400000) / 1000);
END; $$
LANGUAGE PLPGSQL;


-- convert timestamp to Discord snowflake
CREATE OR REPLACE FUNCTION time_snowflake (date TIMESTAMP WITH TIME ZONE)
    RETURNS BIGINT AS $$
BEGIN
    RETURN CAST(EXTRACT(epoch FROM date) * 1000 - 1420070400000 AS BIGINT) << 22;
END; $$
LANGUAGE PLPGSQL;


CREATE TABLE IF NOT EXISTS domains (
    domain_id serial PRIMARY KEY,
    domain text,
    
    -- permissions' bits:
    -- I: image upload permission
    -- S: shorten permission
    -- default is 3 since it is 0b11.
    permissions int DEFAULT 3
);

-- edit this line if you are not elixi.re
INSERT INTO domains (domain_id, domain) VALUES (0, 'elixi.re');

CREATE TABLE IF NOT EXISTS users (
    -- generated snowflake for the user
    user_id bigint PRIMARY KEY,
    username text UNIQUE,

    -- instead of deleting an account right away, for law enforcement
    -- purposes, we can mark is as inactive.
    active boolean DEFAULT true,
    password_hash text,
    email text UNIQUE NOT NULL,
    admin boolean DEFAULT false
);

CREATE TABLE IF NOT EXISTS user_settings (
    user_id bigint REFERENCES users (user_id) ON DELETE CASCADE PRIMARY KEY,

    consented boolean DEFAULT NULL,
    paranoid boolean DEFAULT false NOT NULL,

    subdomain text DEFAULT '' NOT NULL,
    domain bigint REFERENCES domains (domain_id) DEFAULT 0 NOT NULL,

    shorten_subdomain text DEFAULT '' NOT NULL,
    shorten_domain bigint REFERENCES domains (domain_id) DEFAULT NULL,

    default_max_retention bigint DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS admin_user_settings (
    user_id bigint REFERENCES users (user_id) ON DELETE CASCADE,

    audit_log_emails boolean DEFAULT false,

    PRIMARY KEY (user_id)
);

-- This is a new table
-- since we can't afford to make circular depedencies.

-- the other approach would be having domains.owner_id
-- referencing to users, but users already has
-- users.domain and users.shorten_domain already referencing
-- domains.
CREATE TABLE IF NOT EXISTS domain_owners (
    domain_id bigint REFERENCES domains ON DELETE CASCADE,
    user_id bigint REFERENCES users ON DELETE CASCADE NOT NULL,
    PRIMARY KEY (domain_id)
);

-- user and IP bans, usually automatically managed by
-- our ratelimiting code, but can be extended.
CREATE TABLE IF NOT EXISTS bans (
    user_id bigint REFERENCES users (user_id) ON DELETE CASCADE,
    reason text,
    end_timestamp timestamp without time zone
);

CREATE TABLE IF NOT EXISTS ip_bans (
    ip_address text NOT NULL,
    reason text NOT NULL,
    end_timestamp timestamp without time zone,

    -- so we know when the ban happened
    timestamp timestamp without time zone default now()
);

-- upload weekly limits for users
CREATE TABLE IF NOT EXISTS limits (
    user_id bigint REFERENCES users (user_id) ON DELETE CASCADE,
    blimit bigint DEFAULT 104857600, /* byte limit for uploads, 100 mb by default */
    shlimit bigint DEFAULT 100, /* link shorten limit, 100 by default */
    PRIMARY KEY (user_id)
);

CREATE TABLE IF NOT EXISTS files (
    -- another snowflake
    file_id bigint PRIMARY KEY,

    -- so we know what to send instead of filename.split('.')[-1]
    mimetype text,

    -- generated by us, see api/common.py, gen_filename function
    filename text UNIQUE NOT NULL,

    file_size bigint,
    uploader bigint REFERENCES users (user_id) ON DELETE CASCADE,
    
    -- where is the file, inside our filesystem structure
    fspath text,

    -- same reasons as users can be inactive,
    -- files can be *marked* as deleted in the DB.
    deleted boolean DEFAULT false,

    -- files are per domain and subdomain
    domain bigint REFERENCES domains (domain_id) DEFAULT 0,
    subdomain text DEFAULT NULL
);

-- shortened URLs
CREATE TABLE IF NOT EXISTS shortens (
    -- snowflake
    shorten_id bigint PRIMARY KEY,

    -- same as files, gen_filename is used
    filename text UNIQUE NOT NULL,

    -- link this shortened url will redirect to
    redirto text,

    uploader bigint REFERENCES users (user_id) ON DELETE CASCADE,
    deleted boolean DEFAULT false,

    domain bigint REFERENCES domains (domain_id) DEFAULT 0,
    subdomain text DEFAULT NULL
);

-- email stuff for account deletion confirmations
CREATE TABLE IF NOT EXISTS email_deletion_tokens (
    hash text NOT NULL,
    user_id bigint REFERENCES users (user_id) ON DELETE CASCADE,
    expiral timestamp without time zone default now() + interval '12 hours',
    PRIMARY KEY (hash, user_id)
);

-- email stuff for password reset requests
CREATE TABLE IF NOT EXISTS email_pwd_reset_tokens (
    hash text NOT NULL,
    user_id bigint REFERENCES users (user_id) ON DELETE CASCADE,
    expiral timestamp without time zone default now() + interval '30 minutes',
    PRIMARY KEY (hash, user_id)
);

-- email stuff for data dumps
CREATE TABLE IF NOT EXISTS email_dump_tokens (
    hash text NOT NULL,
    user_id bigint REFERENCES users (user_id) ON DELETE CASCADE,
    expiral timestamp without time zone default now() + interval '6 hours',
    PRIMARY KEY (hash, user_id)
);

-- email stuff for account activations
CREATE TABLE IF NOT EXISTS email_activation_tokens (
    hash text NOT NULL,
    user_id bigint REFERENCES users (user_id) ON DELETE CASCADE,
    expiral timestamp without time zone default now() + interval '1 day',
    PRIMARY KEY (hash, user_id)
);

CREATE TABLE IF NOT EXISTS domain_tags (
    tag_id serial PRIMARY KEY,
    label text
);

CREATE TABLE IF NOT EXISTS domain_tag_mappings (
    domain_id bigint REFERENCES domains ON DELETE CASCADE,
    tag_id bigint REFERENCES domain_tags ON DELETE CASCADE,
    PRIMARY KEY (domain_id, tag_id)
);

INSERT INTO domain_tags (label) VALUES ('admin_only');

-- a domain being official means the DNS ownership of it is by
-- the instance owner, keep in mind this isn't the same as Registrar ownership
INSERT INTO domain_tags (label) VALUES ('official');

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

CREATE TABLE IF NOT EXISTS scheduled_delete_queue (
    job_id uuid primary key,
    name text unique,

    state bigint default 0,
    errors text default '',
    inserted_at timestamp without time zone default (now() at time zone 'utc'),
    scheduled_at timestamp without time zone default (now() at time zone 'utc'),
    taken_at timestamp without time zone default null,
    internal_state jsonb default '{}',

    file_id bigint references files (file_id) on delete cascade default null,
    shorten_id bigint references shortens (shorten_id) on delete cascade default null
);
