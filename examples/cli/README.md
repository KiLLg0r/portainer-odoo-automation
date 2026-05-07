# Interactive CLI examples

```bash
python cli.py
```

## Walk-through: update one module across selected staging containers

```
? What do you want to do?
  ❯ Update Odoo module
    Run psql command
    List Portainer environments
    Quit

? Where do the targets come from?
  ❯ Pick from live Portainer list

Fetching containers from Portainer...

? Select containers (space to toggle, enter to confirm):
  [x] odoo-client-a   (staging, running)
  [x] odoo-client-b   (staging, running)
  [ ] odoo-client-a   (prod, running)

? Modules (comma-separated, default: dp_base):  dp_base,sale

? Restart running containers before the update?  Yes

Modules:   dp_base,sale
Restart:   yes
Targets (2):
  - odoo-client-a
  - odoo-client-b

? Proceed?  Yes

Logging to logs/odoo_update_2026-05-07_181203.log
Targets: 2 | initially stopped: []
Running 2 target(s) across 1 env(s), up to 10 concurrent per env.
[env staging] processing 2 container(s)
[restart] odoo-client-a
[restart] odoo-client-b
--- action on odoo-client-a ---
... odoo logs ...
(exit=0)
... etc ...
[env staging] done

[Update Odoo module] finished with exit code 0.

? Run another automation?  No
```

## Walk-through: psql fix from a target file

`targets/prod-eu.txt`:

```
# EU production tenants
odoo-client-a
odoo-client-b
odoo-client-c
```

```
? What do you want to do?  Run psql command
? Where do the targets come from?  Load from file in targets/
? Pick a target file:  prod-eu.txt
? SQL to run (single statement; use --sql in CLI for multi-line):
  UPDATE res_company SET enable_name_update=True WHERE id=1;
? Restart Postgres containers before running?  No

SQL:       UPDATE res_company SET enable_name_update=True WHERE id=1;
Restart:   no
Targets (3):
  - odoo-client-a_db
  - odoo-client-b_db
  - odoo-client-c_db

? Proceed?  Yes
```

## Walk-through: chaining operations

`cli.py` loops by default — at the end of each automation it asks
"Run another automation?". Useful when you want to:

1. **List environments** to confirm what's actually running.
2. **Run psql command** to apply a fix.
3. **Update Odoo module** to pick up a code change.

…all in one session, without re-typing your `.env` or re-fetching the
container list.

Press `Ctrl-C` at any prompt to bail out — the CLI returns exit code
130 and skips the "run another?" question.

## Tips

- **"Live" picker** is the safest source — you see container state
  (`running`, `exited`) before selecting, so you don't accidentally
  start something that was off for a reason.
- **"File" picker** is best for repeated jobs: keep one `.txt` per
  environment / customer group.
- **"Manual" picker** is fine for one-offs; copy-paste names from
  Portainer's UI.
