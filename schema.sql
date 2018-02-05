CREATE TABLE users (
    user_id bigint PRIMARY KEY, /* snowflake */
    active boolean DEFAULT true,
    /* 
    instead of deleting an account (and everything with it),
    we can mark it as inactive.
    */
    username text,
    password_hash text,
    admin boolean DEFAULT false,
    domain bigint REFERENCES domains (domain_id) DEFAULT 0,
);

CREATE TABLE domains (
    domain_id bigint PRIMARY KEY,
    domain text DEFAULT "https://elixi.re/" /* needs to finish with / */
);

INSERT INTO domains (domain_id, domain)
VALUES (0, "https://elixi.re");

/* weekly limits */
CREATE TABLE limits (
    user_id bigint REFERENCES users (user_id) ON DELETE CASCADE,
    limit bigint DEFAULT 104857600, /* 100 mb by default */
);

/* all files */
CREATE TABLE files (
    file_id bigint PRIMARY KEY, /* snowflake */
    file_str text, /* something like "d5Ym" */
    file_size bigint,

    uploader bigint REFERENCES users (user_id) ON DELETE CASCADE,
    path text, /* where the actual file is in fs */
);
