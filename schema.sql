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
    admin_only boolean DEFAULT false,
    cf_enabled boolean DEFAULT false,
    cf_email text,
    cf_zoneid text,
    cf_apikey text,
    domain text
);

INSERT INTO domains (domain_id, domain) VALUES (0, 'elixi.re');

CREATE TABLE IF NOT EXISTS users (
    user_id bigint PRIMARY KEY, /* snowflake */
    username text UNIQUE,
    /* 
    instead of deleting an account (and everything with it),
    we can mark it as inactive.
    */
    active boolean DEFAULT true,
    password_hash text,
    admin boolean DEFAULT false,
    subdomain text DEFAULT '',
    domain bigint REFERENCES domains (domain_id) DEFAULT 0
);

/* User and IP bans */
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

/* weekly limits */
CREATE TABLE IF NOT EXISTS limits (
    user_id bigint REFERENCES users (user_id) ON DELETE CASCADE,
    blimit bigint DEFAULT 104857600, /* byte limit for uploads, 100 mb by default */
    shlimit bigint DEFAULT 100, /* link shorten limit, 100 by default */
    PRIMARY KEY (user_id)
);

/* all files */
CREATE TABLE IF NOT EXISTS files (
    file_id bigint PRIMARY KEY, /* snowflake */
    mimetype text,
    filename text, /* something like "d5Ym" */
    file_size bigint,

    uploader bigint REFERENCES users (user_id) ON DELETE CASCADE,
    fspath text, /* where the actual file is in fs */
    deleted boolean DEFAULT false,
    domain bigint REFERENCES domains (domain_id) DEFAULT 0
);

/* all shortened links */
CREATE TABLE IF NOT EXISTS shortens (
    shorten_id bigint PRIMARY KEY, /* snowflake */
    filename text, /* something like "d5Ym" */
    redirto text, /* the link this shortened link will redirect to */

    uploader bigint REFERENCES users (user_id) ON DELETE CASCADE,
    deleted boolean DEFAULT false,
    domain bigint REFERENCES domains (domain_id) DEFAULT 0
);
