"""Interactive automation: list Portainer environments and containers."""
from __future__ import annotations

from list_environments import main as list_environments_main


LABEL = "List Portainer environments"
DESCRIPTION = "Print all environments and their containers, write environments.json."


def run_interactive() -> int:
    list_environments_main()
    return 0
