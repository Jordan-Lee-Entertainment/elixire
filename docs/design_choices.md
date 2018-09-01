# Design choices

## Why Python?

Our team mostly consists of Python developers.

## Why not Elixir?

While our service is named after Elixir, we think that Elixir isn't designed for
for a mostly HTTP-based application.

While Phoenix and Cowboy do a great job, we find Elixir's process model to be
unnecessary for our use case. (Able to be understood by the majority of
developers is a big reason.)

## Why Sanic and not Flask, aiohttp, etc?

Sanic is asynchronous, unlike Flask, and we find it to be relatively easy to
work with.

## Why PostgreSQL for main storage?

[ACID] is a desirable property in almost all applications. Specifically, in an
image hosting application where your data needs to be consistent and fast.

[acid]: https://en.wikipedia.org/wiki/ACID_(computer_science)

SQLite is a smaller alternative, but it lacks a decent asyncio library to work
with.

## Why Redis?

PostgreSQL is good, but other image hosting solutions had issues with people
spamming their APIs and due to no caching, their SQL servers slowed down.

Redis was the most obvious candidate for caching. After testing in staging, our
read times for certain data dropped significantly.

## Why a single folder?

A single folder to store all files is easy, simple, and straightforward. We
could use Amazon S3 or Backblaze, but this current solution works quite well for
us.
