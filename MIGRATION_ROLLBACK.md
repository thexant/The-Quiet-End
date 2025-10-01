# Database Migration Notes

The Quiet End now ships with a single, supported PostgreSQL backend. The legacy SQLite helpers
(`database_sqlite_backup.py`, `database_old_conversion.py`, and `migration.load`) have been
removed from the repository and are ignored by Git going forward. Rollbacks to SQLite are no
longer maintained.

## Migrating legacy SQLite data

If you are upgrading from an older SQLite deployment:

1. **Export your SQLite data** using `sqlite3 data.sqlite .dump > export.sql` (replace the file
   name with your database).
2. **Review the dump for SQLite-specific syntax** (for example `AUTOINCREMENT`). Update any
   statements that are not valid PostgreSQL SQL. The existing `database.py` module contains
   helper methods you can reference for converting schema definitions.
3. **Import into PostgreSQL**. The recommended approach is to load the exported statements with
   [`pgloader`](https://pgloader.readthedocs.io/) or by piping the adjusted SQL into `psql` once
   your PostgreSQL cluster is running.
4. **Validate the schema** by running `python validate_schema.py` against the live PostgreSQL
   database and confirming the bot starts normally.

If you require the previous rollback script for historical purposes, retrieve it from the project
history rather than expecting it in the current branch.

## Staying on PostgreSQL

PostgreSQL is now the authoritative datastore for the project. Keep regular backups using
`pg_dump` (see `deploy.sh backup`) and avoid committing database data directories or dumps to the
repository. This ensures clean deployments and simpler upgrades.
