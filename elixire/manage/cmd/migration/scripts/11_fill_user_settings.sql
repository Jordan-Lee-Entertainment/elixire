INSERT INTO user_settings (user_id, consented, paranoid, subdomain, domain, shorten_subdomain, shorten_domain)
SELECT user_id, consented, paranoid, subdomain, domain, shorten_subdomain, shorten_domain FROM users;
