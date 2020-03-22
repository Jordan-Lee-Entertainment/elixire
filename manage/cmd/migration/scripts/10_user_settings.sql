CREATE TABLE IF NOT EXISTS user_settings (
    user_id bigint REFERENCES users (user_id) ON DELETE CASCADE PRIMARY KEY,

    consented boolean DEFAULT NULL,
    paranoid boolean DEFAULT false NOT NULL,

    subdomain text DEFAULT '' NOT NULL,
    domain bigint REFERENCES domains (domain_id) DEFAULT 0 NOT NULL,

    shorten_subdomain text DEFAULT '' NOT NULL,
    shorten_domain bigint REFERENCES domains (domain_id) DEFAULT NULL
);
