ALTER TABLE domains
    -- if a domain is owned by the elixire development team
    -- related to GDPR's Right to Information, which talks
    -- about data being processed by people outside of the development team,
    -- domain owners that are not elixi.re, for example.
    ADD COLUMN official BOOLEAN DEFAULT false;

ALTER TABLE users
    -- so we are able to send data dumps(GDPR's Right to Data Portability),
    -- notices about the service on data breaches, etc (GDPR's Right to be informed).
    ADD COLUMN email TEXT NOT NULL;

-- GDPR's Right to Restrict Processing
--  the only kind of processing we found was service statistics.
--  if a user wants to opt out of that processing, a new field is here.

-- meaning of values for the consented field:
--  NULL: not consented YET, present a page with information
--  FALSE: not constented
--  TRUE: consented to processing
ALTER TABLE users
    ADD COLUMN consented BOOLEAN DEFAULT NULL;

