# Elixire backend

This document describes certain backend decisions.
It is written by Luna, the main backend developer.


## Languages and frameworks

### Why Python?

That is the language 2 out of our 3 main developers use daily.

### Why not Elixir to go with the meme?

Elixir was not designed for the task of a mostly HTTP based application.

Yes, Phoenix/Cowboy do a great job, but Elixir's process model doesn't fit in
our requirements. (Able to comprehend by majority of people is the biggest one)

## Why sanic and not flask, aiohttp, etc?

We wanted something that:
 - Uses asyncio (`flask` is out, plus all the other async libraries)
 - Easy to work with (`aiohttp` is out of this)

Sanic fit those two requirements.

## Databases

### Why PostgreSQL for main storage?

ACID is a really desirable property in almost all applications.
Specially in a image hosting scenario where your data needs to be
consistent as fast as possible.

SQLite could be another alternative and a smaller one, but
PostgreSQL is the only with an async library to work with: `asyncpg`.

No. `run_in_executor` is not a solution.

### Redis?

PostgreSQL is good and all, but other image hosting solutions had issues
with people spamming their own APIs and thanks to no caching, their SQL
servers slowed down.

Redis was the most obvious candidate. After testing in staging our read times
for certain data dropped significantly. Deployment in production had some issues at first,
but that is normal with all software development.

## Storage

### Why a single folder?

That is the easiest option to build on since we wanted to develop
more of the "feature" side of elixi.re.

Right now there are some proposals like Amazon S3 and Backblaze B2 backups,
but the current solution works, and quite well.
