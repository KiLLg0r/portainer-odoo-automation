"""Interactive automation: run a psql command in {name}_db containers."""
from __future__ import annotations

from types import SimpleNamespace

import questionary

from portainer_client import client_from_env
from automation_runner import find_targets, setup_logging, run_on_targets
from run_psql import make_psql_action

from ._targets import select_targets
from ._confirm import confirm_and_run


LABEL = "Run psql command"
DESCRIPTION = ("Run an SQL statement inside {name}_db containers, as user "
               "and database {name}.")


def run_interactive() -> int:
    client = client_from_env()
    targets = select_targets(client, suffix_filter="_db")
    if not targets:
        print("No targets selected.")
        return 2

    # Accept either app names or already-suffixed _db names.
    app_names = [n.removesuffix("_db") for n in targets]
    db_names = [f"{n}_db" for n in app_names]

    sql = questionary.text(
        "SQL to run (single statement; use --sql in CLI for multi-line):",
    ).ask()
    if sql is None:
        return 130
    sql = sql.strip()
    if not sql:
        print("Empty SQL — aborting.")
        return 2

    restart = questionary.confirm(
        "Restart Postgres containers before running?",
        default=False,
    ).ask()
    if restart is None:
        return 130

    summary = [
        f"SQL:       {sql}",
        f"Restart:   {'yes' if restart else 'no'}",
        f"Targets ({len(db_names)}):",
        *[f"  - {n}" for n in db_names],
    ]

    def go() -> int:
        ns = SimpleNamespace(log_dir="logs")
        setup_logging(ns, "run_psql")
        resolved = find_targets(client, db_names)
        if not resolved:
            return 2
        failures = run_on_targets(
            client, resolved, make_psql_action(sql),
            no_restart=not restart, per_env_workers=10,
        )
        if failures:
            print(f"\nFailed: {failures}")
            return 1
        return 0

    return confirm_and_run(summary, go)
