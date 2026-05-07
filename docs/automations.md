# Interactive automations

The `cli.py` menu is built from a list of automation modules. Each
module is small (~50 lines), wraps an action with `questionary` prompts,
and reuses the same `run_on_targets` runner the scripts use.

## Module contract

Every file under `automations/` that's wired into `cli.py` exposes:

```python
LABEL: str          # menu entry, shown in questionary.select
DESCRIPTION: str    # one-line hint shown beneath the menu

def run_interactive() -> int:
    """Run the flow, return an exit code."""
```

Exit code semantics match the scripts (see [scripts.md](scripts.md)).
`130` is reserved for "user cancelled" and tells `cli.py` to terminate
the loop instead of asking "run another?".

## Registry

`cli.py` keeps an explicit list:

```python
from automations import odoo_update, psql, list_envs
AUTOMATIONS = [odoo_update, psql, list_envs]
```

Order in the list = order in the menu.

## Adding a new automation

1. **Create the module.** Pick a filename like
   `automations/my_thing.py`. Use one of the existing modules
   (`odoo_update.py`, `psql.py`) as a template.

2. **Define `LABEL`, `DESCRIPTION`, `run_interactive()`.** A typical
   shape:

   ```python
   from types import SimpleNamespace
   import questionary
   from portainer_client import client_from_env
   from automation_runner import find_targets, setup_logging, run_on_targets

   from ._targets import select_targets
   from ._confirm import confirm_and_run

   LABEL = "Do the thing"
   DESCRIPTION = "Run `the thing` on selected containers."

   def my_action(client, c):
       return client.exec_run(c, ["echo", "hello", c.name])

   def run_interactive() -> int:
       client = client_from_env()
       targets = select_targets(client)
       if not targets:
           return 2

       # ... ask for any per-action parameters with questionary ...

       summary = [
           f"Targets ({len(targets)}):",
           *[f"  - {n}" for n in targets],
       ]

       def go() -> int:
           setup_logging(SimpleNamespace(log_dir="logs"), "my_thing")
           resolved = find_targets(client, targets)
           if not resolved:
               return 2
           failures = run_on_targets(
               client, resolved, my_action,
               no_restart=False, per_env_workers=10,
           )
           return 0 if not failures else 1

       return confirm_and_run(summary, go)
   ```

3. **Wire it into `cli.py`.** Add to the import and the list:

   ```python
   from automations import odoo_update, psql, list_envs, my_thing
   AUTOMATIONS = [odoo_update, psql, list_envs, my_thing]
   ```

That's the whole contract. No registration boilerplate, no decorators.

## Shared helpers

### `automations/_targets.py`

```python
def select_targets(client, *, suffix_filter: str | None = None) -> list[str]: ...
```

Prompts the user to pick container names from one of three sources:

- **Manual** — comma-separated text.
- **Live** — multi-select over containers fetched from Portainer
  (filtered by `suffix_filter` if provided, e.g. `"_db"` for psql).
- **File** — pick a `.txt` or `.csv` from `targets/`. For `.txt`, one
  name per line; blank lines and `#` comments ignored. For `.csv`, the
  first column is the container name and the first row is treated as a
  header. Falls back to manual if `targets/` is missing or empty.

Pass `client=None` to disable the "live" option (the `list_envs`
automation doesn't take targets, so it doesn't call this).

### `automations/_confirm.py`

```python
def confirm_and_run(summary_lines: list[str], action: Callable[[], int]) -> int: ...
```

Prints the summary, asks "Proceed? [y/N]", and runs `action()` if
confirmed. Returns the action's exit code, or `0` if cancelled, or `130`
if the user pressed Ctrl-C.

## Reusing script-level action factories

The interactive `odoo_update.py` and `psql.py` modules don't redeclare
the odoo/psql command lists — they import:

```python
from update_odoo_module import make_odoo_update_action
from run_psql import make_psql_action
```

When you add a new automation that maps to a new script, follow the
same pattern: factor the action into a `make_xxx_action(...)` factory in
the script, and have the interactive module import it. One source of
truth for the command line.

## Cancellation handling

`questionary.ask()` returns `None` when the user presses Ctrl-C or
escapes a prompt. Each automation maps that to `return 130`. `cli.py`
sees the `130` and exits the menu loop immediately rather than asking
"run another?".
