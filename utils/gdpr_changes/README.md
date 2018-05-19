Here are (majority) SQL scripts to change the current database(as of b76466fc998f22acdb06eae4b6cd8c67539914d0)
into GDPR. (issues #13, #23 to be more specific).

We have `gdpr_schema_changes_stageN.sql` because we are iterating over and some things haven't been implemented yet.

 - Stage 0 is what we currently have to change, database-wise, for GDPR.

More stages may come as other parts of our GDPR compliance are thought about.
