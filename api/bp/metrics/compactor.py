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
import pprint
import logging

log = logging.getLogger(__name__)

SEC_NANOSEC = 1000000000


MEASUREMENTS = {
    'request': 'request_hour',
    'response': 'response_hour',
    'request_pub': 'request_pub_hour',
    'response_pub': 'response_pub_hour',
    'error': 'error_hour',
    'page_hit': 'page_hit_hour',
}


def extract_row(res: dict, index: int):
    """Extract a single value from a single row.

    This is a helper function for InfluxDB results.
    """
    result = res['results'][0]

    if 'series' not in result:
        return None

    return result['series'][0]['values'][0][index]


def maybe(result: dict) -> list:
    """Get a series of results if they actually are in the influxdb result."""
    return result['series'][0]['values'] if 'series' in result else []


async def _fetch_context(app, meas: str, generalize_sec: int):
    """Fetch the initial context in the compactor.

    This does the first part in the 'Gather' step.
    """
    influx = app.metrics.influx

    query_clauses = f"""
    from {meas}
    where time < now() - {generalize_sec}s
    order by time desc
    """

    # they must be in separate queries.
    first_res = await influx.query(f"""
    select
        first(value)
    {query_clauses}
    """)

    last_res = await influx.query(f"""
    select
        last(value)
    {query_clauses}
    """)

    count_res = await influx.query(f"""
    select
        count(*)
    {query_clauses}
    """)

    count = extract_row(count_res, 1)

    log.info('working %d datapoints for %s',
             count, meas)

    first = extract_row(first_res, 0)
    last = extract_row(last_res, 0)

    return first, last


async def get_chunk_slice(app, meas, start_ts: int,
                          generalize_sec: int) -> tuple:
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
    influx = app.metrics.influx

    start_before_slice = start_ts - (generalize_sec * SEC_NANOSEC)
    end_after_slice = start_ts + (generalize_sec * SEC_NANOSEC)

    before = await influx.query(f"""
    select *
    from {meas}
    where
        time < {start_ts} - 3600s
    and time > {start_before_slice}
    """)

    after = await influx.query(f"""
    select *
    from {meas}
    where
        time > {start_ts}
    and time < {end_after_slice}
    """)

    return maybe(before['results'][0]), maybe(after['results'][0])


async def _update_point(influx, meas: str, timestamp: int, new_val: int):
    """Rewrite a single datapoint in a measurement.

    InfluxDB doesn't provide an 'UPDATE' statement, so I'm rolling out
    with my own.
    """
    await influx.query(f"""
    delete from {meas}
    where time = {timestamp}
    """)

    await influx.write(
        f'{meas} value={new_val}i {timestamp}'
    )


async def pre_process(influx, before: list,
                      target: str, start_ts: int):
    """Pre-process datapoints that should already be in the target."""

    # assert it isn't empty.
    assert bool(before)

    # fetch the existing target
    existing_sum_res = await influx.query(f"""
    select time, value
    from {target}
    where time >= {start_ts}
    limit 1
    """)

    existing_sum_val = extract_row(existing_sum_res, 1)

    log.debug('existing target at ts=%d, res=%r',
              start_ts, existing_sum_val)

    # merge the existing value in the target
    # with the values that didn't make to the target.
    final_sum = existing_sum_val + sum(point[1] for point in before)

    # update it
    await _update_point(influx, target, start_ts, final_sum)


async def submit_chunk(influx, source: str, target: str,
                       chunk_start: int, generalize_sec):
    """Submit a single chunk into target.

    This will fetch all datapoints in the chunk start timestamp,
    sum their values, then insert the newly created datapoint
    in the chunk start timestamp (but on the target measurement, instead
    of the source).
    """
    # last timestamp of this chunk
    chunk_end = chunk_start + (generalize_sec * SEC_NANOSEC)

    # fetch the chunk in the source
    res = await influx.query(f"""
    select time, value
    from {source}
    where
        time > {chunk_start}
    and time < {chunk_end}
    """)

    chunk = maybe(res['results'][0])
    chunk_sum = sum(point[1] for point in chunk)

    log.debug('chunk process, start: %d, end: %d, '
              'total: %d, sum: %d',
              chunk_start, chunk_end, len(chunk), chunk_sum)

    # insert it into target

    await influx.write(
        f'{target} value={chunk_sum}i {chunk_start}'
    )

    return chunk_end



async def main_process(influx, source: str, target: str,
                       start_ts: int, stop_ts: int,
                       generalize_sec: int):
    """Process through the datapoints, submitting each
    chunk to the target.
    """
    chunk_start = start_ts

    while True:
        chunk_end = await submit_chunk(
            influx, source, target,
            chunk_start, generalize_sec
        )

        # if stop_ts is in this chunk, we should stop
        # the loop
        if chunk_start <= stop_ts <= chunk_end:
            return

        # new chunk_start is chunk_end, then go for
        # the next chunk.
        chunk_start = chunk_end


async def compact_single(app, meas: str, target: str):
    """Compact a single measurement.

    Parameters
    ----------
    meas: str
        Source measurement.
    target: str
        Target measurement.
    """
    influx = app.metrics.influx
    generalize_sec = app.econfig.METRICS_COMPACT_GENERALIZE

    # get the first and last timestamps
    # in the datapoints that still exist
    # (Fs and Ts)
    first, last = await _fetch_context(app, meas, generalize_sec)
    log.debug('meas: %s, first: %d, last: %d', meas, first, last)

    # fetch Lt
    last_in_target_res = await influx.query(f"""
    select last(value)
    from {target}
    """)

    last_target = extract_row(last_in_target_res, 0)

    # check values for pre-process
    start_ts = (first
                if last_target is None
                else last_target + generalize_sec)

    log.debug('starting [%s]: f=%d l=%d last_target=%r start_ts=%d',
              meas, first, last, last_target, start_ts)

    # get Bs and As based on Lt
    before, after = await get_chunk_slice(
        app, meas, start_ts, generalize_sec)

    log.debug('there are %d points in Bs', len(before))
    log.debug('there are %d points in As', len(after))

    if before:
        await pre_process(influx, before, target, start_ts)

    # iterative process where we submit chunks to target
    await main_process(
        influx, meas, target,

        # get Las
        min(r[0] for r in after),

        # give it Ts, which is its stop condition
        last,

        generalize_sec
    )


async def compact_task(app):
    """Main compact task.

    Calls compact_single for each
    measurement in MEASUREMENTS.
    """
    for meas, target in MEASUREMENTS.items():
        log.debug('compacting %s -> %s', meas, target)
        await compact_single(app, meas, target)
