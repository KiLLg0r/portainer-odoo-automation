"""Interactive CLI: pick an automation from a menu and run it.

To add a new automation:
  1. Create a module in automations/ exposing LABEL, DESCRIPTION,
     run_interactive() -> int.
  2. Import and append it to the AUTOMATIONS list below.
"""
from __future__ import annotations

import sys
import traceback

import questionary

from automations import odoo_update, psql, list_envs, image_update


AUTOMATIONS = [odoo_update, psql, image_update, list_envs]


def _pick_automation():
    choices = [
        questionary.Choice(title=m.LABEL, value=m, description=m.DESCRIPTION)
        for m in AUTOMATIONS
    ]
    choices.append(questionary.Choice(title="Quit", value=None))
    return questionary.select(
        "What do you want to do?", choices=choices,
    ).ask()


def main() -> int:
    while True:
        try:
            module = _pick_automation()
        except KeyboardInterrupt:
            return 130
        if module is None:
            return 0
        try:
            code = module.run_interactive()
        except KeyboardInterrupt:
            print("\nInterrupted.")
            return 130
        except Exception:
            traceback.print_exc()
            code = 1
        print(f"\n[{module.LABEL}] finished with exit code {code}.\n")

        if code == 130:
            return 130

        again = questionary.confirm("Run another automation?",
                                    default=True).ask()
        if not again:
            return code


if __name__ == "__main__":
    sys.exit(main())
