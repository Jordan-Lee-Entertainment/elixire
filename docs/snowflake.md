# Snowflake

 - We use the same techniques Discord uses to generate their IDs,
 and that format is based off Twitter's implementation for "sequential" IDs (snowflakes).

 - Not truly sequential, but can be unique and can be ordered chronologically.

 - Original implementation assumes multiple workers and processes generating IDs,
 Elixire's implementation assumes 1 process and 1 worker.

 - Elixire's implementation uses global state, which is a bad idea. Might want
 to look into detaching that.
