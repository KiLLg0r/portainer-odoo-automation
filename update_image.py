"""Pull the latest image and recreate containers via the Docker API."""
from __future__ import annotations

import io
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

# Per-endpoint pull locks: concurrent pulls of the same image cause Docker's
# pull-deduplication to close the "follower" response streams prematurely
# (manifests as "Response ended prematurely" in requests). Serialising pulls
# per environment means the first worker does the real pull and the rest get
# a fast "already up-to-date" response, then everyone recreates in parallel.
_pull_locks: dict[int, threading.Lock] = {}
_pull_locks_meta_lock = threading.Lock()


def _get_pull_lock(endpoint_id: int) -> threading.Lock:
    with _pull_locks_meta_lock:
        lock = _pull_locks.get(endpoint_id)
        if lock is None:
            lock = threading.Lock()
            _pull_locks[endpoint_id] = lock
        return lock


def image_update_action(client: PortainerClient,
                        c: Container) -> tuple[int, str]:
    buf = io.StringIO()

    def w(line: str) -> None:
        buf.write(line + "\n")

    was_running = c.state == "running"
    w(f"State:  {'running' if was_running else 'stopped'}")

    inspect = client.inspect_container(c)
    # Use Config.Image — the named reference (e.g. registry/image:tag).
    # c.image from list_containers may be a SHA digest on some Docker versions.
    image = inspect["Config"]["Image"]
    w(f"Image:  {image}")

    w(f"Pulling {image}...")
    with _get_pull_lock(c.endpoint_id):
        client.pull_image(c.endpoint_id, image)
    w("Pull complete.")

    body = dict(inspect["Config"])
    body["HostConfig"] = inspect["HostConfig"]
    body["NetworkingConfig"] = {
        "EndpointsConfig": inspect["NetworkSettings"]["Networks"]
    }

    if was_running:
        w("Stopping...")
        client.stop(c)

    w("Removing old container...")
    client.remove_container(c)

    w("Creating new container...")
    new_id = client.create_container(c.endpoint_id, c.name, body)
    w(f"Created {new_id[:12]}.")

    if was_running:
        new_c = Container(
            id=new_id, name=c.name, state="created",
            image=image,
            endpoint_id=c.endpoint_id, endpoint_name=c.endpoint_name,
        )
        w("Starting...")
        client.start(new_c)
        if not client.wait_running(new_c, timeout=config.WAIT_RUNNING_TIMEOUT):
            w(f"ERROR: did not reach running state within "
              f"{config.WAIT_RUNNING_TIMEOUT}s")
            return 1, buf.getvalue()
        w("Running.")

    return 0, buf.getvalue()


def _run_one(client: PortainerClient,
             c: Container) -> tuple[str, bool]:
    buf = io.StringIO()
    failed = False
    try:
        code, output = image_update_action(client, c)
        buf.write(output)
        if code != 0:
            failed = True
    except Exception as e:
        buf.write(f"ERROR: {e}\n")
        failed = True
    with _print_lock:
        sys.stdout.write(f"\n===== {c.name} =====\n")
        sys.stdout.write(buf.getvalue())
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
        "Pull the latest image and recreate containers via the Docker API."
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
