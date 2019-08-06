ALTER TABLE files
    ADD COLUMN subdomain text DEFAULT NULL;

-- files are now only accessible on the subdomain that they were uploaded on,
-- however files that were updated before this change need to stay accessible
-- on both the root domain and any subdomain. this is signalled using an empty
-- string for the subdomain.
UPDATE files
    SET subdomain = '';

ALTER TABLE shortens
    ADD COLUMN subdomain text DEFAULT NULL;

-- (see above comment)
UPDATE shortens
    SET subdomain = '';
