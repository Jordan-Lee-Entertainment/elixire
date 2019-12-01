ALTER TABLE bans
    ADD COLUMN timestamp timestamp without time zone default now();
