CREATE TABLE IF NOT EXISTS admin_user_settings (
    user_id bigint REFERENCES users (user_id) ON DELETE CASCADE,

    audit_log_emails boolean DEFAULT false,

    PRIMARY KEY (user_id)
);
