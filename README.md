# portainer-odoo-automation

A small toolkit for running per-container automations across a fleet of
Odoo deployments managed through Portainer. Useful when you have a
dozen+ Odoo instances and need to update modules, run a SQL fix, or
audit environments without clicking through Portainer for each one.

Two ways to use it: an **interactive CLI** for ad-hoc work, and
**plain scripts** for cron / non-interactive runs. Both share the same
guarantee — containers stopped before the run are stopped again
afterwards.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # if you don't have a .env yet
```

Required: `PORTAINER_URL` and either an API key or username+password.
See [docs/configuration.md](docs/configuration.md) for all auth options
(including nginx basic auth in front of Portainer).

## Usage

```bash
python cli.py
```

Pick an action from the menu:

- **Update Odoo module** — runs `odoo -u <modules>` on selected
  containers (default `dp_base`, accepts a comma-separated list).
- **Run psql command** — runs an SQL statement inside `{name}_db`
  containers.
- **List Portainer environments** — prints all environments and their
  containers, writes `environments.json`.

For each action you choose targets from one of three sources:

- **Manual** — type comma-separated names.
- **Live** — multi-select from a list fetched from Portainer.
- **File** — pick a `.txt` file from `targets/` (one name per line,
  `#` comments ignored).

A summary is shown before any work starts; nothing runs until you
confirm.

## Going further

For non-interactive use, see the three scripts in the project root —
they accept `--targets a,b,c` and other flags. For everything else
(architecture, configuration, adding new automations) start at
[`docs/`](docs/README.md).
