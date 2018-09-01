# Snowflakes

We use the same technique that Discord and Twitter use to generate IDs. While
these IDs are not truly sequential, they are unique and chronologically ordered.
A snowflake functions as both a unique identifier and a timestamp. We find this
to be convenient.

## Implementation details

While the original implementation assumes multiple workers and processes
generating IDs, elixi.re's implementation assumes 1 process and worker.

Global state is used for ID incrementation.
