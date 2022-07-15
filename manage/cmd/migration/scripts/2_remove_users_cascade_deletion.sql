-- this keeps our database consistency safer against buggy deletions
-- of the users table.

-- as business logic now must delete other tables willingly before deleting
-- the user itself

-- we only do this to our most important tables that must hold data after
-- a user deletion, which are files, shortens

BEGIN;

ALTER TABLE files
    DROP CONSTRAINT IF EXISTS files_uploader_fkey,
    ADD CONSTRAINT files_uploader_fkey
        FOREIGN KEY (uploader)
        REFERENCES users (user_id)
        ON DELETE RESTRICT;

ALTER TABLE shortens
    DROP CONSTRAINT IF EXISTS shortens_uploader_fkey,
    ADD CONSTRAINT shortens_uploader_fkey
        FOREIGN KEY (uploader)
        REFERENCES users (user_id)
        ON DELETE RESTRICT;

COMMIT;
