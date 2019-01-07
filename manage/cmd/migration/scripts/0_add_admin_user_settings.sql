CREATE TABLE IF NOT EXISTS admin_user_settings (
    user_id bigint REFERENCES users (user_id) ON DELETE CASCADE,

    email_flags bigint,

    PRIMARY KEY (user_id)
);
