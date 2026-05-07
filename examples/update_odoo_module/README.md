# `update_odoo_module.py` examples

Default action: `odoo -c /etc/odoo/odoo.conf -u dp_base -p 9999 --stop-after-init -d <name>`.

To change the default module list, edit the call to
`make_odoo_update_action(["dp_base"])` in
[`update_odoo_module.py`](../../update_odoo_module.py)'s `main()`.

## Update one module across two clients

```bash
python update_odoo_module.py --targets odoo-client-a,odoo-client-b
```

Runs the default `dp_base` update. Restarts each running container
first. Initially-stopped containers are stopped again at the end.

## Update without bouncing running containers

```bash
python update_odoo_module.py --targets odoo-client-a --no-restart
```

Skips the pre-update restart. Useful when you trust the running state
and just want the module update applied.

## Limit concurrency per environment

```bash
python update_odoo_module.py --targets odoo-client-a,odoo-client-b,odoo-client-c \
    --per-env-workers 2
```

Up to 2 containers per environment run in parallel. Default is 10.
Lower values reduce load on each Portainer host.

## Cron / unattended runs

```cron
# Update dp_base on EU prod every Sunday at 03:00
0 3 * * 0  cd /opt/portainer-automation && \
    /usr/bin/python update_odoo_module.py --targets $(cat targets/prod-eu.txt | tr '\n' ',') \
    >> logs/cron.log 2>&1
```

Or, simpler, edit the `TARGETS` list in
[`update_odoo_module.py`](../../update_odoo_module.py) and drop the
`--targets` flag:

```python
TARGETS = ["odoo-client-a", "odoo-client-b"]
```

## Sample target file

`targets/prod-eu.txt` (used together with the interactive CLI):

```
# EU production tenants
odoo-client-a
odoo-client-b
odoo-client-c
```

(See [`prod-eu.txt`](prod-eu.txt) in this folder.)

## Exit codes

| Code | Meaning |
|---|---|
| `0` | All containers updated |
| `1` | One or more containers failed (names listed in the log) |
| `2` | No targets given, or no matching containers found |
