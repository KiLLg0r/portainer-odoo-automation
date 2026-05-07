# `run_psql.py` examples

Runs `psql -U {name} -d {name} -c "<sql>"` inside `{name}_db` containers
(append/strip `_db` is handled automatically — pass APP names).

Defaults to `--no-restart` because restarting Postgres mid-fleet is
usually a bad idea.

## Enable a setting on one tenant

```bash
python run_psql.py --targets odoo-client-a \
    --sql "UPDATE res_company SET enable_name_update=True WHERE id=1;"
```

## Same fix across many tenants

```bash
python run_psql.py \
    --targets odoo-client-a,odoo-client-b,odoo-client-c \
    --sql "UPDATE res_company SET enable_name_update=True WHERE id=1;"
```

Each container's `_db` companion is exec'd in parallel (per env, capped
by `--per-env-workers`).

## Structured shortcut for trivial updates

```bash
python run_psql.py --targets odoo-client-a \
    --table res_company --set enable_name_update=True --where "id=1"
```

Builds `UPDATE res_company SET enable_name_update=True WHERE id=1;`.
Booleans/`NULL`/numeric values pass through unquoted; strings are
single-quoted with `'` escaping. For anything else (functions,
sub-selects, multi-column updates) use `--sql`.

## Read-only check

`run_psql.py` also accepts SELECTs and prints their output to the log:

```bash
python run_psql.py --targets odoo-client-a \
    --sql "SELECT id, name FROM res_company ORDER BY id LIMIT 5;"
```

Useful as a "did the update land?" sanity check after the destructive
run.

## Multiple statements

`psql -c` accepts multiple `;`-terminated statements:

```bash
python run_psql.py --targets odoo-client-a \
    --sql "BEGIN; UPDATE res_company SET enable_name_update=True WHERE id=1; COMMIT;"
```

## Sample target file

`targets/all-prod.txt`:

```
# All production tenants (EU + US)
odoo-client-a
odoo-client-b
odoo-client-c
odoo-client-us-1
odoo-client-us-2
```

(See [`all-prod.txt`](all-prod.txt) in this folder.)

## Exit codes

| Code | Meaning |
|---|---|
| `0` | All `psql` invocations succeeded (exit 0) |
| `1` | At least one `psql` exited non-zero |
| `2` | Bad invocation (no targets, missing/conflicting flags, no matching `_db` containers) |
