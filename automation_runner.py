"""Shared scaffolding for per-container automations against Portainer.

Provides logging, target lookup, argparse defaults, and a runner that
ensures each target is running, dispatches a user-supplied action with
per-environment parallelism, and restores initially-stopped containers
on the way out.
"""
from __future__ import annotations

import argparse
import io
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Callable

from portainer_client import PortainerClient, Container
import config


_print_lock = threading.Lock()

Action = Callable[[PortainerClient, Container], tuple[int, str]]


def log(msg: str = "", err: bool = False) -> None:
    stream = sys.stderr if err else sys.stdout
    with _print_lock:
        stream.write(msg + "\n")
        stream.flush()


class Tee:
    """Write to multiple streams (e.g. stdout + log file)."""
    def __init__(self, *streams):
        self.streams = streams

    def write(self, data):
        for s in self.streams:
            s.write(data)
            s.flush()

    def flush(self):
        for s in self.streams:
            s.flush()


def find_targets(client: PortainerClient,
                 names: list[str]) -> list[Container]:
    wanted = set(names)
    found: dict[str, Container] = {}
    for _, containers in client.get_all(exclude_local=True).items():
        for c in containers:
            if c.name in wanted and c.name not in found:
                found[c.name] = c
    missing = wanted - set(found)
    if missing:
        print(f"WARNING: not found: {sorted(missing)}", file=sys.stderr)
    return list(found.values())


def make_argparser(description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--targets", help="Comma-separated container names "
                                          "(overrides TARGETS in the script).")
    parser.add_argument("--restart", action=argparse.BooleanOptionalAction,
                        default=True,
                        help="Restart running containers before the action "
                             "(default: True). Pass --no-restart to skip.")
    parser.add_argument("--log-dir", default="logs",
                        help="Directory for log files (default: ./logs).")
    parser.add_argument("--per-env-workers", type=int,
                        default=config.PER_ENV_WORKERS_DEFAULT,
                        help=f"Max concurrent containers per environment "
                             f"(default: {config.PER_ENV_WORKERS_DEFAULT}).")
    return parser


def setup_logging(args: argparse.Namespace, script_name: str) -> str:
    # Reset to the originals first so repeated calls (e.g. from the
    # interactive CLI looping over automations) don't stack Tee wrappers.
    sys.stdout = sys.__stdout__
    sys.stderr = sys.__stderr__
    os.makedirs(args.log_dir, exist_ok=True)
    log_path = os.path.join(
        args.log_dir,
        f"{script_name}_{datetime.now():%Y-%m-%d_%H%M%S}.log",
    )
    log_file = open(log_path, "w", encoding="utf-8", errors="replace")
    sys.stdout = Tee(sys.__stdout__, log_file)
    sys.stderr = Tee(sys.__stderr__, log_file)
    print(f"Logging to {log_path}")
    return log_path


def _process_target(client: PortainerClient, c: Container,
                    action: Action, no_restart: bool) -> tuple[str, bool]:
    """Per-container worker. Ensure running, run action, buffer all output,
    and flush atomically under _print_lock so parallel containers don't
    interleave line-by-line."""
    buf = io.StringIO()

    def w(s: str) -> None:
        buf.write(s + "\n")

    failed = False
    try:
        if c.state != "running":
            w(f"[start]   {c.name}")
            client.start(c)
        elif not no_restart:
            w(f"[restart] {c.name}")
            client.restart(c)

        if not client.wait_running(c, timeout=config.WAIT_RUNNING_TIMEOUT):
            w(f"ERROR: {c.name} did not reach running state")
            failed = True

        w(f"--- action on {c.name} ---")
        try:
            code, output = action(client, c)
        except Exception as e:
            w(f"EXEC ERROR on {c.name}: {e}")
            return c.name, True
        w(output)
        w(f"(exit={code})")
        if code != 0:
            failed = True
    except Exception as e:
        w(f"UNEXPECTED ERROR on {c.name}: {e}")
        failed = True

    with _print_lock:
        sys.stdout.write(f"\n===== {c.name} =====\n")
        sys.stdout.write(buf.getvalue())
        sys.stdout.flush()
    return c.name, failed


def run_on_targets(client: PortainerClient,
                   targets: list[Container],
                   action: Action,
                   *, no_restart: bool,
                   per_env_workers: int) -> list[str]:
    """Ensure-running → per-env parallel action → restore stopped.
    Returns names of containers that failed."""
    if not targets:
        return []
    initially_stopped = [c for c in targets if c.state != "running"]
    print(f"Targets: {len(targets)} | initially stopped: "
          f"{[c.name for c in initially_stopped]}")

    per_env_workers = max(1, per_env_workers)
    by_env: dict[str, list[Container]] = {}
    for c in targets:
        by_env.setdefault(c.endpoint_name, []).append(c)

    print(f"Running {len(targets)} target(s) across {len(by_env)} env(s), "
          f"up to {per_env_workers} concurrent per env.")

    failures: list[str] = []
    failures_lock = threading.Lock()

    def run_env(env_name: str, group: list[Container]) -> None:
        log(f"[env {env_name}] processing {len(group)} container(s)")
        with ThreadPoolExecutor(
            max_workers=min(per_env_workers, len(group)),
            thread_name_prefix=f"env-{env_name}",
        ) as pool:
            for name, failed in pool.map(
                lambda c: _process_target(client, c, action, no_restart),
                group,
            ):
                if failed:
                    with failures_lock:
                        failures.append(name)
        log(f"[env {env_name}] done")

    with ThreadPoolExecutor(
        max_workers=len(by_env), thread_name_prefix="env-dispatch",
    ) as outer:
        list(outer.map(lambda kv: run_env(kv[0], kv[1]), by_env.items()))

    if initially_stopped:
        print(f"\nStopping {len(initially_stopped)} initially-stopped "
              f"container(s)...")
        stopped_by_env: dict[str, list[Container]] = {}
        for c in initially_stopped:
            stopped_by_env.setdefault(c.endpoint_name, []).append(c)

        def _stop(c: Container) -> None:
            try:
                client.stop(c)
                log(f"[stop]    {c.name} (was initially stopped)")
            except Exception as e:
                log(f"STOP ERROR on {c.name}: {e}", err=True)

        def stop_env(group: list[Container]) -> None:
            with ThreadPoolExecutor(
                max_workers=min(per_env_workers, len(group))
            ) as pool:
                list(pool.map(_stop, group))

        with ThreadPoolExecutor(max_workers=len(stopped_by_env)) as outer:
            list(outer.map(stop_env, stopped_by_env.values()))

    return failures
