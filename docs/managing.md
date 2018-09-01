Managing your elixi.re instance
--------------------------------

## Tooling

 - If you built the Elixire Admin Panel (EAD), and you're currently logged in
    an admin account in your instance, go to the `/admin` path in your website
    to access it, from there you can find user, domain and file administration.

 - `./manage.py` Is a general management script made to superseed the scripts
 on the `utils/` directory. `./manage.py help` and `./manage.py help <operation>` to
 find out how to use it.
    - Keep in mind `./manage.py` won't integrate functions from the Admin API into it
      (that might change in the future).

 - Misc scripts can be found under the `utils/` directory.
   - `utils/stats.py` runs through your database to process information about your instance.
      Since elixi.re is GDPR compliant, we show two types of statistics: Public and Private.
      You should not disclose any Private statistics to anyone other than your development team,
      as doing so can bring you under GDPR violation. Private statistics still exist to determine
      the quality of service (e.g too many files, image folder getting big, etc).

   - `utils/resetpasswd.py` to reset a single user's password *manually.*


 - Scripts for old instances to be brought into the current version of elixi.re can be found
 under the `utils/upgrade` directory.
   - **Do not run those scripts if you don't need them.**

   - `utils/upgrade/folder_sharding.py` is for instances that had the old system of all images
      in a single image directory. This "shards" the image folder and moves each file into
      its respective folder (`./images/<first character of filename>/<filename>`, e.g `./images/a/abc.png`).

   - `utils/upgrade/storage_filehash.py` is for instances that are on the old system that
      doesn't include file hashes as part of the folder structure.


## d1

[d1](https://gitlab.com/elixire/d1) is a domain checker. More information can be found
on the project's URL. It is recommended for production enviroments with lots of domains
to have d1 running. Set `SECRET_KEY` on your config if you want to enable d1.


## Metrics

elixi.re can send metric information to InfluxDB, from there Grafana can show you the data
in pretty form so you can visualize instance information better.
