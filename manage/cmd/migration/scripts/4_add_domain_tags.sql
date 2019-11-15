CREATE TABLE IF NOT EXISTS tag_list (
    tag_id serial PRIMARY KEY,
    label text
);

CREATE TABLE IF NOT EXISTS domain_tags (
    domain_id bigint REFERENCES domains ON DELETE CASCADE,
    tag_id bigint REFERENCES tag_list ON DELETE CASCADE,
    PRIMARY KEY (domain_id, tag_id)
);
