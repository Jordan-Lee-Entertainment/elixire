BEGIN;

ALTER TABLE scheduled_delete_queue
    DROP CONSTRAINT scheduled_delete_queue_file_id_fkey,
    ADD CONSTRAINT scheduled_delete_queue_file_id_fkey
        FOREIGN KEY (file_id)
        REFERENCES files (file_id)
        ON DELETE CASCADE;

ALTER TABLE scheduled_delete_queue
    DROP CONSTRAINT scheduled_delete_queue_shorten_id_fkey,
    ADD CONSTRAINT scheduled_delete_queue_shorten_id_fkey
        FOREIGN KEY (shorten_id)
        REFERENCES shortens (shorten_id)
        ON DELETE CASCADE;

COMMIT;
