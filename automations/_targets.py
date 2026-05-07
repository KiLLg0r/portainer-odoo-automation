"""Shared target picker for interactive automations.

Three sources:
- manual: comma-separated text input
- live:   multi-select from containers fetched via Portainer
- file:   pick a .txt file from the targets/ directory
"""
from __future__ import annotations

from pathlib import Path

import questionary

from portainer_client import PortainerClient


TARGETS_DIR = Path("targets")


def _from_manual() -> list[str]:
    raw = questionary.text(
        "Container names (comma-separated):"
    ).ask()
    if raw is None:
        return []
    return [n.strip() for n in raw.split(",") if n.strip()]


def _from_live(client: PortainerClient,
               suffix_filter: str | None) -> list[str]:
    print("Fetching containers from Portainer...")
    by_env = client.get_all(exclude_local=True)
    choices: list[str] = []
    name_lookup: dict[str, str] = {}
    for env_name, containers in by_env.items():
        for c in containers:
            if suffix_filter and not c.name.endswith(suffix_filter):
                continue
            display = f"{c.name}  ({env_name}, {c.state})"
            choices.append(display)
            name_lookup[display] = c.name
    if not choices:
        suffix_msg = f" matching suffix '{suffix_filter}'" if suffix_filter else ""
        print(f"No containers found{suffix_msg}.")
        return []
    choices.sort()
    selected = questionary.checkbox(
        "Select containers (space to toggle, enter to confirm):",
        choices=choices,
    ).ask()
    if selected is None:
        return []
    return [name_lookup[s] for s in selected]


def _from_file() -> list[str]:
    if not TARGETS_DIR.is_dir():
        print(f"No '{TARGETS_DIR}/' directory found. "
              "Falling back to manual entry.")
        return _from_manual()
    files = sorted(p.name for p in TARGETS_DIR.iterdir() if p.suffix == ".txt")
    if not files:
        print(f"No .txt files in '{TARGETS_DIR}/'. "
              "Falling back to manual entry.")
        return _from_manual()
    pick = questionary.select("Pick a target file:", choices=files).ask()
    if pick is None:
        return []
    path = TARGETS_DIR / pick
    names: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        names.append(line)
    return names


def select_targets(client: PortainerClient | None,
                   *, suffix_filter: str | None = None) -> list[str]:
    """Prompt the user to pick container names from one of three sources.
    Returns the selected list (possibly empty if the user cancelled or
    nothing matched)."""
    choices = ["Type names manually", "Pick from live Portainer list",
               "Load from file in targets/"]
    if client is None:
        choices.remove("Pick from live Portainer list")
    pick = questionary.select("Where do the targets come from?",
                              choices=choices).ask()
    if pick is None:
        return []
    if pick == "Type names manually":
        return _from_manual()
    if pick == "Pick from live Portainer list":
        return _from_live(client, suffix_filter)
    if pick == "Load from file in targets/":
        return _from_file()
    return []
