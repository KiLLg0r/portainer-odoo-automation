"""For each name in TARGETS: ensure `{name}_db` is running, exec a psql
command (`psql -U {name} -d {name} -c <sql>`), then restore any
container that was initially stopped.

SQL is supplied either via --sql (raw) or via --table/--set/--where
(structured shortcut that builds a single UPDATE statement)."""
from __future__ import annotations

import re
import sys
import time
from datetime import timedelta

from portainer_client import client_from_env, Container, PortainerClient
from automation_runner import (
    find_targets, make_argparser, setup_logging, run_on_targets,
)


# Edit this list, or pass --targets name1,name2 on the CLI.
# Pass APP container names (e.g. "odoo-client-a"); the script looks up
# "odoo-client-a_db" automatically.
TARGETS: list[str] = [
    # "odoo-client-a",
]


_NUMERIC_RE = re.compile(r"^-?\d+(\.\d+)?$")
_UNQUOTED = {"true", "false", "null"}


def quote_value(v: str) -> str:
    """Naive SQL literal quoting for the structured form."""
    low = v.lower()
    if low == "null":
        return "NULL"
    if low in _UNQUOTED:
        return v.capitalize()
    if _NUMERIC_RE.match(v):
        return v
    return "'" + v.replace("'", "''") + "'"


def build_sql(args) -> str:
    if args.sql:
        return args.sql
    if not (args.table and args.set and args.where):
        raise SystemExit(
            "Must pass either --sql or all of --table, --set, --where."
        )
    if "=" not in args.set:
        raise SystemExit("--set must be FIELD=VALUE")
    field, _, value = args.set.partition("=")
    return (f"UPDATE {args.table} SET {field}={quote_value(value)} "
            f"WHERE {args.where};")


def make_psql_action(sql: str):
    """Build a per-container action that runs
    `psql -U {name} -d {name} -c <sql>` inside the {name}_db container."""
    def psql_action(client: PortainerClient,
                    c: Container) -> tuple[int, str]:
        user = c.name.removesuffix("_db")
        cmd = ["psql", "-U", user, "-d", user, "-c", sql]
        return client.exec_run(c, cmd)
    return psql_action


def main() -> int:
    started = time.monotonic()
    parser = make_argparser(
        "Run a psql command against the {name}_db container for each "
        "target. Default --no-restart (avoid bouncing Postgres)."
    )
    parser.set_defaults(restart=False)
    parser.add_argument("--sql",
                        help="Raw SQL statement to run via psql -c.")
    parser.add_argument("--table",
                        help="Structured form: table name.")
    parser.add_argument("--set",
                        help="Structured form: FIELD=VALUE.")
    parser.add_argument("--where",
                        help="Structured form: WHERE expression.")
    args = parser.parse_args()
    setup_logging(args, "run_psql")

    if args.sql and (args.table or args.set or args.where):
        print("--sql is mutually exclusive with --table/--set/--where.",
              file=sys.stderr)
        return 2
    sql = build_sql(args)
    print(f"SQL: {sql}")

    names = (args.targets.split(",") if args.targets else TARGETS)
    names = [n.strip() for n in names if n.strip()]
    if not names:
        print("No targets. Set TARGETS in the script or pass --targets.",
              file=sys.stderr)
        return 2

    db_names = [f"{n.removesuffix('_db')}_db" for n in names]

    client = client_from_env()
    targets = find_targets(client, db_names)
    if not targets:
        return 2

    failures = run_on_targets(
        client, targets, make_psql_action(sql),
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
