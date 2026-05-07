# Scriptable scripts

Three scripts that can be run from the CLI or cron, independent of the
interactive menu. They share the same flags, log format, and container
lifecycle (see [architecture.md](architecture.md)).

## `update_odoo_module.py`

Runs `odoo -c /etc/odoo/odoo.conf -u dp_base -p 9999 --stop-after-init -d <name>`
inside each target container.

```bash
python update_odoo_module.py --targets odoo-client-a,odoo-client-b
python update_odoo_module.py --targets odoo-client-a --no-restart
```

Defaults to **restarting** running containers before the update. Pass
`--no-restart` to skip.

The action is built by `make_odoo_update_action(modules: list[str])`,
which is what the interactive flow uses with a user-chosen module list.
The script itself always passes `["dp_base"]`. To change the default
permanently, edit the call in `main()`.

## `run_psql.py`

Runs `psql -U {name} -d {name} -c "<sql>"` inside `{name}_db` containers.
You pass APP container names via `--targets`; the script appends `_db`
itself, and is idempotent if you accidentally pass `_db`-suffixed names
already.

```bash
# Raw SQL — most flexible
python run_psql.py --targets odoo-client-a \
    --sql "UPDATE res_company SET enable_name_update=True WHERE id=1;"

# Structured shortcut — single UPDATE statement
python run_psql.py --targets odoo-client-a \
    --table res_company --set enable_name_update=True --where "id=1"
```

`--sql` and `--table/--set/--where` are mutually exclusive.

Defaults to `--no-restart` (Postgres should not be bounced). Pass
`--restart` to override.

The structured form does **naive** SQL literal quoting:

| Input | Output |
|---|---|
| `True`, `false`, `null` | `True`, `False`, `NULL` (unquoted) |
| `42`, `-3.14` | unquoted |
| anything else | single-quoted, with `'` doubled (e.g. `O'Brien` → `'O''Brien'`) |

For anything beyond simple values, use `--sql`. The structured form is
not a SQL-injection-safe quoter — it's a convenience wrapper for
`UPDATE … SET field=value WHERE expr` against your own DB.

## `list_environments.py`

Lists all non-local Portainer environments and their containers, writes
a `environments.json` snapshot.

```bash
python list_environments.py
```

No flags. Useful as a reality check before running other scripts.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | All targets succeeded |
| `1` | One or more targets failed (names listed in the log) |
| `2` | Bad invocation (no targets, mutually-exclusive flags, no matching containers, …) |
