-- Add columns that modify domain behavior.
ALTER TABLE domains
    ADD COLUMN disabled BOOLEAN DEFAULT FALSE NOT NULL;

-- Delete tags that modify domain behavior.
DELETE FROM domain_tags WHERE label = 'admin_only';
