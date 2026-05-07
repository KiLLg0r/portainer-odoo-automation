# poartainer-odoo-automation

Small Python toolkit for running per-container automations against a
fleet of Odoo deployments managed through Portainer. Two ways to use
it: an **interactive CLI** for ad-hoc operations, and **scriptable
scripts** for cron / non-interactive runs.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # if you don't have a .env yet
```

Required env vars (see `portainer_client.client_from_env`):

- `PORTAINER_URL` (required)
- `PORTAINER_API_KEY` **or** `PORTAINER_USERNAME` + `PORTAINER_PASSWORD`
- Optional: `PORTAINER_VERIFY_SSL`,
  `PORTAINER_BASIC_AUTH_USER`, `PORTAINER_BASIC_AUTH_PASSWORD`

## Interactive CLI

```bash
python cli.py
```

Pick an action from the menu:

- **Update Odoo module** — runs `odoo -u <modules>` across selected
  containers. Defaults to `dp_base`; accepts a comma-separated list.
- **Run psql command** — runs an SQL statement inside `{name}_db`
  containers as user / database `{name}`.
- **List Portainer environments** — prints all environments and their
  containers, writes `environments.json`.

For each action, you choose targets from one of three sources:

- **Manual** — type comma-separated names.
- **Live** — multi-select from a list fetched from Portainer.
- **File** — pick a `.txt` file from `targets/`. One name per line;
  blank lines and lines starting with `#` are ignored.

A summary is shown before any work starts; nothing runs until you
confirm.

### Adding a new automation

1. Create `automations/<your_module>.py` exposing:
   - `LABEL: str` — menu entry.
   - `DESCRIPTION: str` — one-line hint.
   - `run_interactive() -> int` — runs the flow, returns an exit code.
2. Import it and append it to `AUTOMATIONS` in `cli.py`.

## Scriptable scripts

Each script supports `--targets a,b,c` to override its hardcoded
`TARGETS` list, plus shared flags: `--restart` / `--no-restart`,
`--log-dir`, `--per-env-workers`.

### `update_odoo_module.py`

Runs `odoo -c /etc/odoo/odoo.conf -u dp_base -p 9999 --stop-after-init
-d <name>` against each target. Restarts running containers first by
default; pass `--no-restart` to skip. Initially-stopped containers are
restored to stopped at the end.

```bash
python update_odoo_module.py --targets odoo-client-a,odoo-client-b
```

### `run_psql.py`

Runs `psql -U <name> -d <name> -c "<sql>"` inside `<name>_db` containers.
Pass APP container names via `--targets`; the script appends `_db`
itself (idempotent if you already pass `_db` names). Defaults to
`--no-restart` (Postgres should not be bounced).

```bash
# Raw SQL
python run_psql.py --targets odoo-client-a \
    --sql "UPDATE res_company SET enable_name_update=True WHERE id=1;"

# Structured shortcut (single UPDATE statement)
python run_psql.py --targets odoo-client-a \
    --table res_company --set enable_name_update=True --where "id=1"
```

### `list_environments.py`

Lists all non-local environments and their containers, writes
`environments.json`.

```bash
python list_environments.py
```

## Logs

Every script writes a timestamped log to `logs/`
(`{script}_{YYYY-MM-DD_HHMMSS}.log`). The interactive CLI uses the same
log files as the underlying scripts.

## Project layout

```
automation_runner.py    Shared scaffolding: argparse, logging, run_on_targets.
portainer_client.py     Thin Portainer API wrapper.
update_odoo_module.py   Script + factory: make_odoo_update_action(modules).
run_psql.py             Script + factory: make_psql_action(sql).
list_environments.py    List endpoints and containers.
cli.py                  Interactive entry point.
automations/            One module per interactive automation.
  _targets.py             Shared target picker.
  _confirm.py             Shared confirmation prompt.
  odoo_update.py
  psql.py
  list_envs.py
targets/                Place .txt files here for the file-based picker.
```
