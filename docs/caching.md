# Caching

Caching in the service is handled by Redis.

We cache user, file, and domain information for quick access.

All caching is done by the storage subsystem located in `api/storage.py`. It is
an abstraction that works on top of Postgres and Redis to only fetch data from
the database when necessary.

## Cached information

A non-comprehensive list of information we cache in Redis:

- **Users**
  - Username → User ID
  - User ID → Username
  - IP bans
  - User bans
- **Authentication**
  - Password hash
  - User active
- **Files**
  - File paths
  - Shorten targets
- **Domains**
  - Domain → Domain ID
