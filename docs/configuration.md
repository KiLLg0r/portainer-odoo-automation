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

If Portainer sits behind nginx with HTTP basic auth (which adds an
`Authorization: Basic …` header that Portainer would otherwise reject in
combination with its own auth), set:

| Var | Notes |
|---|---|
| `PORTAINER_BASIC_AUTH_USER` | nginx basic-auth username |
| `PORTAINER_BASIC_AUTH_PASSWORD` | nginx basic-auth password |
| `PORTAINER_USERNAME` + `PORTAINER_PASSWORD` | **required** alongside basic auth — the client logs in to obtain a JWT and passes it via the `portainer_api_key` cookie (the same way the UI does). API key alone won't work behind basic auth. |

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

## Hardcoded values

These are fixed for the current deployment but easy to parameterize if
you need to reuse the toolkit elsewhere.

| Value | Where | Suggested env var (not yet implemented) |
|---|---|---|
| Odoo config path `/etc/odoo/odoo.conf` | [`update_odoo_module.py`](../update_odoo_module.py) | `ODOO_CONF_PATH` |
| Odoo HTTP port `9999` | [`update_odoo_module.py`](../update_odoo_module.py) | `ODOO_HTTP_PORT` |
| Default modules `dp_base` | [`update_odoo_module.py`](../update_odoo_module.py) `main()` | `ODOO_DEFAULT_MODULES` |
| DB container suffix `_db` | [`run_psql.py`](../run_psql.py), [`automations/psql.py`](../automations/psql.py) | `DB_CONTAINER_SUFFIX` |
| `psql -U {name} -d {name}` (user = db = container basename) | [`run_psql.py`](../run_psql.py) `make_psql_action` | could be templated |
| `wait_running` timeout `120s` | [`automation_runner.py`](../automation_runner.py) `_process_target` | `WAIT_RUNNING_TIMEOUT` |
| Targets directory `targets/` | [`automations/_targets.py`](../automations/_targets.py) `TARGETS_DIR` | `TARGETS_DIR` |

## Target files

For the file-based picker in the interactive CLI:

- Drop `.txt` files in `targets/`.
- One container name per line.
- Blank lines are ignored.
- Lines starting with `#` are ignored (comments).

If `targets/` is missing or empty, the picker falls back to manual entry.
