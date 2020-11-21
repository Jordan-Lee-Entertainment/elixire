# elixire metrics with InfluxDB

elixire currently exports metrics using InfluxDB. The following metrics are
pushed:

- requests per second
- responses per second
- response latency
- upload processing latency
- files uploaded per hour
- size of the entire images/ folder (calculated via the database, not fully correct)
- user counts
- how many "tries" were made to generate a given shortname

# working with per-second metrics in the long term

It might be interesting for elixire sysadmins to hold historical data on request
counts. For example, to see which hour would be the least disruptive for some
major upgrade of the instance.

Issue is, when visualizing such data (e.g with Grafana), it is highly likely
the InfluxDB machine will slow down a lot as it attempts to send over all the
data.

Thankfully, InfluxDB has tooling such that you can downsample request data
so that it's still useful in the long term.
[InfluxDB documentation on this](https://docs.influxdata.com/influxdb/v1.8/guides/downsample_and_retain/)

We have written helper scripts so that you can downsample request data.

**Please review the script before running it.** You may need to change
influx database names: `ON "elixire"` to `ON "your_database"`

Load the script as such: `cat docs/influxdb/cq.influx | influx`

You can visualize if the scripts are loaded up by issuing the command
`SHOW CONTINUOUS QUERIES` inside the InfluxDB shell.

**WARNING:** It is _possible_ that the given queries will not work. There is not
any "migration" system inside InfluxDB so that we could ensure all datapoints
are of same type, or something else. **You will need to look at the InfluxDB
logs to ensure the query ran successfully.** As the queries are timed to run
on every hour, you need only to get the logs at any `XY:00` hour of the day.

For example, on Void Linux, you can search for the continuous query logs with
`svlogtail daemon | grep continuous_`.

## Grafana and InfluxDB

For data visualization, we use Grafana. You may use a different tool for such,
but this section is Grafana-specific.

### "Grafana Queries" for metrics

### Short-term metrics

It should look like this for responses. Requests are the same, but without the
group-by-tag-status.

```
FROM <source> response WHERE [nothing]
SELECT field(value) count()
GROUP BY time(1s) tag(route) tag(status)
FORMAT AS Time series
ALIAS BY [[tag_route]] [[tag_status]]
```

### Long-term metrics

It should look like this for responses. Requests are the same, but without the
group-by-tag-status.

```
FROM <source> response_hour WHERE [nothing]
SELECT field(value) distinct()
GROUP BY time(1m) tag(route) tag(status)
FORMAT AS Time series
ALIAS BY [[tag_route]] [[tag_status]]
```
