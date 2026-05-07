"""For each container in TARGETS: ensure running, exec
`odoo -u dp_base`, then restore initially-stopped containers."""
from __future__ import annotations

import sys
import time
from datetime import timedelta

from portainer_client import client_from_env, Container, PortainerClient
from automation_runner import (
    find_targets, make_argparser, setup_logging, run_on_targets,
)


# Edit this list, or pass --targets name1,name2 on the CLI.
TARGETS: list[str] = [
    # "odoo-client-a",
    # "odoo-client-b",
]


def make_odoo_update_action(modules: list[str]):
    """Build an action that runs `odoo -u <modules>` against a container."""
    modules_arg = ",".join(modules)

    def odoo_update_action(client: PortainerClient,
                           c: Container) -> tuple[int, str]:
        cmd = [
            "odoo",
            "-c", "/etc/odoo/odoo.conf",
            "-u", modules_arg,
            "-p", "9999",
            "--stop-after-init",
            "-d", c.name,
        ]
        return client.exec_run(c, cmd)

    return odoo_update_action


def main() -> int:
    started = time.monotonic()
    parser = make_argparser(
        "Run `odoo -u dp_base` across a set of Odoo containers."
    )
    args = parser.parse_args()
    setup_logging(args, "odoo_update")

    names = (args.targets.split(",") if args.targets else TARGETS)
    names = [n.strip() for n in names if n.strip()]
    if not names:
        print("No targets. Set TARGETS in the script or pass --targets.",
              file=sys.stderr)
        return 2

    client = client_from_env()
    targets = find_targets(client, names)
    if not targets:
        return 2

    failures = run_on_targets(
        client, targets, make_odoo_update_action(["dp_base"]),
        no_restart=not args.restart,
        per_env_workers=args.per_env_workers,
    )

    elapsed = timedelta(seconds=round(time.monotonic() - started))
    if failures:
        print(f"\nFailed: {failures}", file=sys.stderr)
        print(f"Elapsed: {elapsed}")
        return 1
    print(f"\nDone. Elapsed: {elapsed}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
