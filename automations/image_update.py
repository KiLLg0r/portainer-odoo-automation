"""Interactive automation: pull latest image and recreate containers."""
from __future__ import annotations

from types import SimpleNamespace

from portainer_client import client_from_env
from automation_runner import find_targets, setup_logging
from update_image import run_image_update_on_targets
import config

from ._targets import select_targets
from ._confirm import confirm_and_run


LABEL = "Update container image"
DESCRIPTION = "Pull the latest Docker image and recreate containers."


def run_interactive() -> int:
    client = client_from_env()
    targets = select_targets(client)
    if not targets:
        print("No targets selected.")
        return 2

    summary = [
        "Action:  pull latest image + recreate",
        f"Targets ({len(targets)}):",
        *[f"  - {n}" for n in targets],
    ]

    def go() -> int:
        ns = SimpleNamespace(log_dir="logs")
        setup_logging(ns, "image_update")
        resolved = find_targets(client, targets)
        if not resolved:
            return 2
        failures = run_image_update_on_targets(
            client, resolved,
            per_env_workers=config.PER_ENV_WORKERS_DEFAULT,
        )
        if failures:
            print(f"\nFailed: {failures}")
            return 1
        return 0

    return confirm_and_run(summary, go)
