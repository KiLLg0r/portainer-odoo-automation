# `list_environments.py` examples

```bash
python list_environments.py
```

No flags. Prints every non-local Portainer environment and its
containers, then writes a `environments.json` snapshot in the project
root.

## Sample output

```
=== staging (12 containers) ===
  [running   ] odoo-client-a   (odoo:17.0)
  [running   ] odoo-client-a_db (postgres:15)
  [exited    ] odoo-client-old (odoo:16.0)
  ...

=== prod-eu (24 containers) ===
  [running   ] odoo-client-b   (odoo:17.0)
  [running   ] odoo-client-b_db (postgres:15)
  ...

Wrote environments.json
```

## Use case: pre-flight check

Run this before any destructive operation to confirm:

- Which environments are reachable.
- Which containers are running vs stopped.
- Whether a container name you're about to target actually exists.

## Use case: feeding other tools

`environments.json` is a structured dump:

```json
{
  "staging": [
    {"id": "abc123…", "name": "odoo-client-a",
     "state": "running", "image": "odoo:17.0"},
    ...
  ],
  "prod-eu": [...]
}
```

Pipe it to `jq` for ad-hoc queries:

```bash
# All running odoo containers across all envs
python list_environments.py >/dev/null
jq -r 'to_entries[] | .value[] | select(.state=="running" and (.image|startswith("odoo"))) | .name' \
    environments.json

# Containers with "_db" suffix (psql targets)
jq -r 'to_entries[] | .value[] | select(.name|endswith("_db")) | .name' \
    environments.json
```
