ALTER TABLE ip_bans
    ALTER COLUMN ip_address TYPE CIDR USING ip_address::CIDR;
