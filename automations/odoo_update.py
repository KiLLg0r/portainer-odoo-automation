"""Interactive automation: run `odoo -u <modules>` across containers."""
from __future__ import annotations

from types import SimpleNamespace

import questionary

from portainer_client import client_from_env
from automation_runner import find_targets, setup_logging, run_on_targets
from update_odoo_module import make_odoo_update_action
import config

from ._targets import select_targets
from ._confirm import confirm_and_run


LABEL = "Update Odoo module"
DESCRIPTION = "Run `odoo -u <modules>` against a set of containers."


def run_interactive() -> int:
    client = client_from_env()
    targets = select_targets(client)
    if not targets:
        print("No targets selected.")
        return 2

    default_modules = ",".join(config.ODOO_DEFAULT_MODULES)
    modules_input = questionary.text(
        f"Modules (comma-separated, default: {default_modules}):"
    ).ask()
    if modules_input is None:
        return 130
    modules = [m.strip() for m in modules_input.split(",") if m.strip()]
    if not modules:
        modules = list(config.ODOO_DEFAULT_MODULES)

    restart = questionary.confirm(
        "Restart running containers before the update?",
        default=True,
    ).ask()
    if restart is None:
        return 130

    summary = [
        f"Modules:   {','.join(modules)}",
        f"Restart:   {'yes' if restart else 'no'}",
        f"Targets ({len(targets)}):",
        *[f"  - {n}" for n in targets],
    ]

    def go() -> int:
        ns = SimpleNamespace(log_dir="logs")
        setup_logging(ns, "odoo_update")
        resolved = find_targets(client, targets)
        if not resolved:
            return 2
        failures = run_on_targets(
            client, resolved, make_odoo_update_action(modules),
            no_restart=not restart,
            per_env_workers=config.PER_ENV_WORKERS_DEFAULT,
        )
        if failures:
            print(f"\nFailed: {failures}")
            return 1
        return 0

    return confirm_and_run(summary, go)
