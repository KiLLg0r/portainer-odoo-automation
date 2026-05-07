# Architecture

How the pieces fit together.

## Layers

```
                ┌────────────────────────────┐
                │           cli.py           │  interactive entry
                └─────────────┬──────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
   automations/         update_odoo_module.py    run_psql.py    list_environments.py
   odoo_update.py       (script + factory)       (script + factory)
   psql.py
   list_envs.py
        │                     │                     │
        └─────────────────────┴─────────────────────┘
                              │
                              ▼
                    automation_runner.py
                    (find_targets, setup_logging,
                     run_on_targets)
                              │
                              ▼
                    portainer_client.py
                    (auth, list, control, exec)
                              │
                              ▼
                       Portainer API
```

- **`portainer_client.py`** — thin wrapper over the Portainer HTTP API.
  Handles auth (API key / username+password / behind nginx basic auth),
  CSRF priming, listing endpoints and containers, start/stop/restart,
  and `exec` (which the actions use to run commands inside containers).
- **`automation_runner.py`** — the orchestration layer. Exposes
  `find_targets`, `make_argparser`, `setup_logging`, and
  `run_on_targets(client, targets, action, *, no_restart, per_env_workers)`.
  All actual work goes through `run_on_targets`.
- **`update_odoo_module.py` / `run_psql.py`** — single-purpose scripts.
  Each defines an *action* (a `(client, container) -> (exit_code, output)`
  callable, often built by a factory like `make_odoo_update_action(modules)`
  or `make_psql_action(sql)`) and a thin `main()` that wires argparse →
  `run_on_targets` → exit code.
- **`automations/`** — interactive wrappers. Each module exposes
  `LABEL`, `DESCRIPTION`, `run_interactive() -> int` and reuses the same
  action factories from the script files. No command-list duplication.
- **`cli.py`** — top-level menu over `AUTOMATIONS = [odoo_update, psql, list_envs]`.

## Container lifecycle

Every action — script or interactive — runs through `run_on_targets`
([automation_runner.py](../automation_runner.py)), which guarantees:

1. Containers that are stopped get **started**, then waited until
   `state == "running"` (timeout 120s).
2. Containers that are already running get **restarted** — unless
   `--no-restart` (or `restart=False` in interactive mode) is set.
   Default is `restart=True` for `update_odoo_module` and `False` for
   `run_psql` (Postgres should not be bounced).
3. The action runs against the now-running container via
   `client.exec_run(container, cmd)`.
4. Per-container output is buffered and flushed under a lock so parallel
   runs don't interleave line-by-line.
5. When all actions finish, **initially-stopped containers are stopped
   again** in parallel per environment, restoring the original state.

## Concurrency

`run_on_targets` groups targets by `endpoint_name` (each Portainer
environment is typically a separate server) and runs:

- An **outer pool** with one worker per environment — environments
  always run in parallel.
- An **inner pool** per environment with up to `per_env_workers`
  containers concurrently (default 10, configurable via `--per-env-workers`).

Stop/restore at the end uses the same shape (parallel per env, capped by
`per_env_workers`).

## Logging

`setup_logging(args, script_name)` opens `logs/{script_name}_{YYYY-MM-DD_HHMMSS}.log`
and Tees both `sys.stdout` and `sys.stderr` to it. Repeated calls (e.g.
when the interactive CLI runs multiple automations in one session) reset
to the original streams first, so Tee wrappers don't stack.

Output for each container is buffered in an `io.StringIO` and flushed in
one block under a `_print_lock` — so multi-container parallel runs
produce readable, non-interleaved logs.

## Action contract

```python
Action = Callable[[PortainerClient, Container], tuple[int, str]]
```

An action receives a Portainer `Container` and returns
`(exit_code, combined_output)`. Anything that fits this contract can be
plugged into `run_on_targets`. Action factories close over per-run
parameters (modules list, SQL string) and return the actual action.
