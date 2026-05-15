"""Pull the latest image and recreate containers via Portainer's recreate API."""
from __future__ import annotations

import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from portainer_client import client_from_env, Container, PortainerClient
from automation_runner import find_targets, make_argparser, setup_logging
import config


TARGETS: list[str] = [
    # "odoo-client-a",
    # "odoo-client-b",
]

_print_lock = threading.Lock()


def image_update_action(client: PortainerClient,
                        c: Container) -> tuple[int, str]:
    client.recreate_container(c, pull_image=True)
    return 0, "Recreated."


def _run_one(client: PortainerClient,
             c: Container) -> tuple[str, bool]:
    try:
        code, output = image_update_action(client, c)
        failed = code != 0
    except Exception as e:
        output = f"ERROR: {e}"
        failed = True
    with _print_lock:
        sys.stdout.write(f"\n===== {c.name} =====\n{output}\n")
        sys.stdout.flush()
    return c.name, failed


def run_image_update_on_targets(
    client: PortainerClient,
    targets: list[Container],
    per_env_workers: int,
) -> list[str]:
    """Recreate targets with pulled image. Returns names of failed containers."""
    if not targets:
        return []
    by_env: dict[str, list[Container]] = {}
    for c in targets:
        by_env.setdefault(c.endpoint_name, []).append(c)
    print(f"Targets: {len(targets)} across {len(by_env)} environment(s), "
          f"up to {per_env_workers} concurrent per env.")

    failures: list[str] = []
    failures_lock = threading.Lock()

    def run_env(env_name: str, group: list[Container]) -> None:
        with ThreadPoolExecutor(
            max_workers=min(per_env_workers, len(group)),
            thread_name_prefix=f"env-{env_name}",
        ) as pool:
            for name, failed in pool.map(
                lambda c: _run_one(client, c), group
            ):
                if failed:
                    with failures_lock:
                        failures.append(name)

    with ThreadPoolExecutor(
        max_workers=len(by_env), thread_name_prefix="env-dispatch",
    ) as outer:
        list(outer.map(lambda kv: run_env(kv[0], kv[1]), by_env.items()))

    return failures


def main() -> int:
    started = time.monotonic()
    parser = make_argparser(
        "Pull the latest image and recreate containers via Portainer."
    )
    args = parser.parse_args()
    setup_logging(args, "image_update")

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

    failures = run_image_update_on_targets(
        client, targets,
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
