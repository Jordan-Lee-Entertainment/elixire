ALTER TABLE files
    ADD COLUMN subdomain text DEFAULT NULL;

ALTER TABLE shortens
    ADD COLUMN subdomain text DEFAULT NULL;
