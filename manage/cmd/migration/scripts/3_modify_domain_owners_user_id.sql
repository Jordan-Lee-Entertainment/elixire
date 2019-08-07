-- original table:
-- CREATE TABLE IF NOT EXISTS domain_owners (
--     domain_id bigint REFERENCES domains (domain_id) PRIMARY KEY,
--     user_id bigint REFERENCES users (user_id)
-- );

ALTER TABLE domain_owners
  DROP CONSTRAINT IF EXISTS domain_owners_domain_id_fkey,
  DROP CONSTRAINT IF EXISTS domain_owners_user_id_fkey,
  -- add a "on delete cascade"
  ADD CONSTRAINT domain_owners_domain_id_fkey
    FOREIGN KEY (domain_id)
    REFERENCES domains
    ON DELETE CASCADE,
  -- add a "on delete cascade"
  ADD CONSTRAINT domain_owners_user_id_fkey
    FOREIGN KEY (user_id)
    REFERENCES users
    ON DELETE CASCADE,
  -- prevent user_id from being null
  ALTER COLUMN user_id SET NOT NULL;

-- end table:
--
-- CREATE TABLE IF NOT EXISTS domain_owners (
--     domain_id bigint REFERENCES domains ON DELETE CASCADE,
--     user_id bigint REFERENCES users ON DELETE CASCADE NOT NULL,
--     PRIMARY KEY (domain_id)
-- );
