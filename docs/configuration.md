# Configuration

What you can set without changing code, and what's hardcoded today.

## Environment variables

Loaded by `python-dotenv` from a `.env` file in the project root, or
exported in your shell. Read by
[`portainer_client.client_from_env`](../portainer_client.py).

### Auth — pick exactly one strategy

| Var | Required for | Notes |
|---|---|---|
| `PORTAINER_URL` | always | e.g. `https://portainer.example.com` |
| `PORTAINER_API_KEY` | API-key auth | Sent as `X-API-Key`. **Cannot** be combined with nginx basic auth. |
| `PORTAINER_USERNAME` + `PORTAINER_PASSWORD` | login auth | Logs in via `/api/auth`, gets a JWT, sends `Authorization: Bearer …`. |

### Behind an nginx basic-auth wall

If Portainer sits behind nginx (or any reverse proxy) with HTTP basic
auth — which adds an `Authorization: Basic …` header that Portainer
would otherwise reject in combination with its own auth — set:

| Var | Notes |
|---|---|
| `NGINX_BASIC_AUTH_USER` | reverse-proxy basic-auth username |
| `NGINX_BASIC_AUTH_PASSWORD` | reverse-proxy basic-auth password |
| `PORTAINER_USERNAME` + `PORTAINER_PASSWORD` | **required** alongside basic auth — the client logs in to obtain a JWT and passes it via the `portainer_api_key` cookie (the same way the UI does). API key alone won't work behind basic auth. |

`PORTAINER_BASIC_AUTH_USER` / `PORTAINER_BASIC_AUTH_PASSWORD` are kept
as legacy aliases and still work.

### Other

| Var | Default | Notes |
|---|---|---|
| `PORTAINER_VERIFY_SSL` | `true` | Set to `false` to skip TLS verification (e.g. self-signed certs). |

## CLI flags (shared)

Every script supports:

| Flag | Default | Effect |
|---|---|---|
| `--targets a,b,c` | (uses `TARGETS` in the script) | Override hardcoded target list. |
| `--restart` / `--no-restart` | `--restart` for odoo, `--no-restart` for psql | Restart already-running containers before the action. |
| `--log-dir DIR` | `logs` | Where timestamped log files go. |
| `--per-env-workers N` | `10` | Max concurrent containers per environment. |

Plus per-script flags — see [scripts.md](scripts.md).

## Tunable defaults (env-driven)

All values default to the project's original hardcoded values, so
unsetting them everywhere reproduces today's behavior. Defined and
loaded in [`config.py`](../config.py).

### Odoo

| Var | Default | Notes |
|---|---|---|
| `ODOO_CONF_PATH` | `/etc/odoo/odoo.conf` | Passed as `odoo -c …`. |
| `ODOO_HTTP_PORT` | `9999` | Passed as `odoo -p …`. |
| `ODOO_DEFAULT_MODULES` | `dp_base` | Comma-separated. Used when `update_odoo_module.py` is run with no `--targets` override and no interactive override. |

### psql / DB containers

| Var | Default | Notes |
|---|---|---|
| `DB_CONTAINER_SUFFIX` | `_db` | DB container is `{app_name}{suffix}`. Change to `-postgres`, `-pg`, etc. |
| `PSQL_USER_TEMPLATE` | `{name}` | `{name}` is the app container name (without the suffix). Use e.g. `odoo` for a fixed admin user. |
| `PSQL_DB_TEMPLATE` | `{name}` | Same templating as the user. |

### Runner

| Var | Default | Notes |
|---|---|---|
| `WAIT_RUNNING_TIMEOUT` | `120` (seconds) | How long to wait for `state == "running"` after a start/restart. |
| `PER_ENV_WORKERS_DEFAULT` | `10` | Default for `--per-env-workers`; the CLI flag wins when explicitly set. |

### Still hardcoded

| Value | Where | Why |
|---|---|---|
| Targets directory `targets/` | [`automations/_targets.py`](../automations/_targets.py) `TARGETS_DIR` | Convention; rarely worth changing. |
| Default `--log-dir` `logs` | [`automation_runner.py`](../automation_runner.py) `make_argparser` | Already overridable per-run via `--log-dir`. |

## Target files

For the file-based picker in the interactive CLI. Drop files into
`targets/` — both `.txt` and `.csv` are picked up. Contents of
`targets/` are gitignored except `.gitkeep`, so user-specific lists
won't accidentally land in the repo.

### `.txt`

- One container name per line.
- Blank lines are ignored.
- Lines starting with `#` are ignored (comments).

```
# EU production tenants
odoo-client-a
odoo-client-b
```

### `.csv`

- The **first column** holds the container name. Header name irrelevant.
- The **first row is treated as a header** and skipped.
- Other columns are ignored — useful for human-readable metadata
  (env, owner, notes).
- Empty cells, blank rows, and rows whose first cell starts with `#`
  are skipped.

```csv
name,env,owner
odoo-client-a,staging,team-a
odoo-client-b,prod,team-b
# odoo-client-c,prod,disabled
```

If `targets/` is missing or contains no `.txt`/`.csv` files, the picker
falls back to manual entry.
