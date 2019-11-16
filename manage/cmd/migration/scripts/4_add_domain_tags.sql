CREATE TABLE IF NOT EXISTS domain_tags (
    tag_id serial PRIMARY KEY,
    label text
);

CREATE TABLE IF NOT EXISTS domain_tag_mappings (
    domain_id bigint REFERENCES domains ON DELETE CASCADE,
    tag_id bigint REFERENCES domain_tags ON DELETE CASCADE,
    PRIMARY KEY (domain_id, tag_id)
);
