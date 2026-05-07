"""Shared confirmation prompt for interactive automations."""
from __future__ import annotations

from typing import Callable

import questionary


def confirm_and_run(summary_lines: list[str],
                    action: Callable[[], int]) -> int:
    """Show a summary, ask y/N, run the action if confirmed.
    Returns the action's exit code, or 0 if the user cancelled."""
    print()
    for line in summary_lines:
        print(line)
    print()
    ok = questionary.confirm("Proceed?", default=False).ask()
    if ok is None:
        return 130
    if not ok:
        print("Cancelled.")
        return 0
    return action()
