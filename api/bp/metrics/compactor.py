"""
Metrics Compactor

This generates per-hour metrics based on per-second metrics.

Contexts:
     - In InfluxDB, "measurements" feel like "tables" from SQL.

     - For the current elixire setup, each measurement is composed
    of a timestamp(in NANOSECONDS) and its value
    (any kind, but usually its a number).

     - Each pair of (timestamp, value) is called a datapoint.

For each measurement we want to compact, we run through steps,
fetching its datapoints and running simple sum(value) through them.

It isn't as simple as it sounds.

Specific context:
    - The per-second measurement we're working on is called the
    "source" / S.

    - The per-X measurement we're writing sum()'d values on
    is called the "target" / T.

    - X, for all intents and purposes, is 1 hour.

Here's how it looks

S:                [ | | | | | | | | | ]
                  ^                   ^
                  |                   |
                  Fs                  Ts
T: [ | | | | | | | ]
                 ^
                 |
                 Lt

(yes, it is not lined up, that's the worst case
 scenario, so we'll work with that)

Note: chunks in T are just single datapoints,
 while chunks in S have a start and end with
 any amount of datapoints.

each whitespace represents a chunk of datapoints.
they're evenly spaced per hour (3600 seconds)

Steps:

    - Gather:
      - fetch the first and last timestamps from S (Fs, Ts)
      - fetch the last timestamp in T (Lt)

    - Pre Process
      - from Lt, we'll split the first chunk of S in two (Bs, As).
        - we'll add the values in Bs to the chunk specified in Lt
      - if Lt doesn't exist (maybe because T is empty), we do Lt = Fs
        - that way, Bs will be empty.

    - Process
      - From As, we get the first timestamp in it (Las)
      - Then, we fetch all datapoints that are in the range [Las, Las + X]
      - With that chunk [Las, Las + X], we sum their values, and
        insert the result into T, with timestamp Las.
      - Go to the next chunk, Las + X + 1, and repeat the process

      - Stop when Ts is in the range [Las + X * N, Las + X * N+1].

    - Cleanup
      - Delete all datapoints in S that are older than Y.
         (Y, for the example config file, is 10 days.)

"""
import logging

log = logging.getLogger(__name__)

SEC_NANOSEC = 1000000000


MEASUREMENTS = {
    "request": "request_hour",
    "response": "response_hour",
    "request_pub": "request_pub_hour",
    "response_pub": "response_pub_hour",
    "error": "error_hour",
    "page_hit": "page_hit_hour",
}


class CompactorContext:
    """Holds data for a single compactor pass
    in a measurement."""

    def __init__(self, influx, source: str, target: str, generalize_sec: int):
        self.influx = influx
        self.source = source
        self.target = target
        self.generalize_sec = generalize_sec

    @property
    def generalize_nsec(self):
        return self.generalize_sec * SEC_NANOSEC


def extract_row(res: dict, index: int):
    """Extract a single value from a single row.

    This is a helper function for InfluxDB results.
    """
    result = res["results"][0]

    if "series" not in result:
        return None

    return result["series"][0]["values"][0][index]


def maybe(result: dict) -> list:
    """Get a series of results if they actually are in the influxdb result."""
    return result["series"][0]["values"] if "series" in result else []


async def _fetch_init_ctx(ctx: CompactorContext):
    """Fetch the initial context in the compactor.

    This does the first part in the 'Gather' step.
    """
    query_clauses = f"""
    from {ctx.source}
    where time < now() - {ctx.generalize_sec}s
    order by time desc
    """

    # they must be in separate queries.
    first_res = await ctx.influx.query(
        f"""
    select
        first(value)
    {query_clauses}
    """
    )

    last_res = await ctx.influx.query(
        f"""
    select
        last(value)
    {query_clauses}
    """
    )

    count_res = await ctx.influx.query(
        f"""
    select
        count(*)
    {query_clauses}
    """
    )

    count = extract_row(count_res, 1)

    log.info("working %d datapoints for %r", count, ctx.source)

    first = extract_row(first_res, 0)
    last = extract_row(last_res, 0)

    return first, last


async def get_chunk_slice(ctx: CompactorContext, start_ts: int) -> tuple:
    """Split a chunk between before/after counterparts.

    Example:

    (Spacing is 3600 seconds, 1 hour)
    [     |      |     |     ]
                 ^
                 |
                 T

    calling get_chunk_slice with T as the parameter will
    fetch points in the ranges

     - [T - 3600, T] (the "before" points, Bs)
     - [T, T + 3600] (the "after" points, As)
    """
    start_before_slice = start_ts - (ctx.generalize_sec * SEC_NANOSEC)
    end_after_slice = start_ts + (ctx.generalize_sec * SEC_NANOSEC)

    before = await ctx.influx.query(
        f"""
    select *
    from {ctx.source}
    where
        time < {start_ts} - 3600s
    and time > {start_before_slice}
    """
    )

    after = await ctx.influx.query(
        f"""
    select *
    from {ctx.source}
    where
        time > {start_ts}
    and time < {end_after_slice}
    """
    )

    return maybe(before["results"][0]), maybe(after["results"][0])


async def _update_point(ctx, meas: str, timestamp: int, new_val: int):
    """Rewrite a single datapoint in a measurement.

    InfluxDB doesn't provide an 'UPDATE' statement, so I'm rolling out
    with my own.

    This only works with integer updates.
    """
    await ctx.influx.query(
        f"""
    delete from {meas}
    where time = {timestamp}
    """
    )

    await ctx.influx.write(f"{meas} value={new_val}i {timestamp}")


async def pre_process(ctx: CompactorContext, before: list, start_ts: int):
    """Pre-process datapoints that should already be in the target."""

    # assert it isn't empty.
    assert bool(before)

    # fetch the existing target
    existing_sum_res = await ctx.influx.query(
        f"""
    select time, value
    from {ctx.target}
    where time >= {start_ts}
    limit 1
    """
    )

    existing_sum_val = extract_row(existing_sum_res, 1)

    log.debug("existing target at ts=%d, res=%r", start_ts, existing_sum_val)

    # merge the existing value in the target
    # with the values that didn't make to the target.
    final_sum = existing_sum_val + sum(point[1] for point in before)

    # update it
    await _update_point(ctx, ctx.target, start_ts, final_sum)


async def submit_chunk(ctx: CompactorContext, chunk_start: int):
    """Submit a single chunk into target.

    This will fetch all datapoints in the chunk start timestamp,
    sum their values, then insert the newly created datapoint
    in the chunk start timestamp (but on the target measurement, instead
    of the source).
    """
    # last timestamp of this chunk
    chunk_end = chunk_start + ctx.generalize_nsec

    # fetch the chunk in the source
    res = await ctx.influx.query(
        f"""
    select sum(value), count(value)
    from {ctx.source}
    where
        time > {chunk_start}
    and time < {chunk_end}
    """
    )

    rowlist = maybe(res["results"][0])

    # only process the chunk if we actually got results to start with.
    # we most probably *have* results (even if they're 0s), but i don't want
    # to risk type errors (oh, crystal, why have you tainted my soul)
    if rowlist:
        _time, chunk_sum, chunk_count = rowlist[0]

        log.debug(
            "chunk process, start: %d, end: %d, total: %d, sum: %d",
            chunk_start,
            chunk_end,
            chunk_count,
            chunk_sum,
        )

        # insert it into target
        await ctx.influx.write(f"{ctx.target} value={chunk_sum}i {chunk_start}")

    return chunk_end


async def main_process(ctx: CompactorContext, start_ts: int, stop_ts: int):
    """Process through the datapoints, submitting each
    chunk to the target.
    """
    chunk_start = start_ts

    while True:
        chunk_end = await submit_chunk(ctx, chunk_start)

        # if stop_ts is in this chunk, we should stop
        # the loop
        if chunk_start <= stop_ts <= chunk_end:
            return

        # new chunk_start is chunk_end, then go for
        # the next chunk.
        chunk_start = chunk_end


async def compact_single(ctx: CompactorContext):
    """Compact a single measurement."""

    # get the first and last timestamps
    # in the datapoints that still exist
    # (Fs and Ts)
    first, last = await _fetch_init_ctx(ctx)
    log.debug("source: %r, first: %d, last: %d", ctx.source, first, last)

    # fetch Lt
    last_in_target_res = await ctx.influx.query(
        f"""
    select last(value)
    from {ctx.target}
    """
    )

    last_target = extract_row(last_in_target_res, 0)

    # check values for pre-process
    start_ts = first if last_target is None else last_target + ctx.generalize_sec

    log.debug(
        "starting [%s]: f=%d l=%d last_target=%r start_ts=%d",
        ctx.source,
        first,
        last,
        last_target,
        start_ts,
    )

    # get Bs and As based on Lt
    before, after = await get_chunk_slice(ctx, start_ts)

    log.debug("there are %d points in Bs", len(before))
    log.debug("there are %d points in As", len(after))

    if before:
        await pre_process(ctx, before, start_ts)

    # we can't really work without any datapoints
    if not after:
        log.warning("no points in As, skipping %s", ctx.source)

        del before
        del after
        return

    # iterative process where we submit chunks to target
    await main_process(
        ctx,
        # give the start_ts, Las
        min(r[0] for r in after),
        # give it Ts, which is its stop condition
        last,
    )

    del before
    del after


async def compact_task(app):
    """Main compact task.

    Calls compact_single for each
    measurement in MEASUREMENTS.
    """
    for meas, target in MEASUREMENTS.items():
        log.debug("compacting %s -> %s", meas, target)

        ctx = CompactorContext(
            app.metrics.influx, meas, target, app.econfig.METRICS_COMPACT_GENERALIZE
        )

        await compact_single(ctx)
        del ctx
