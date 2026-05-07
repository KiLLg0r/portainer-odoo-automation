"""Script 1: list all non-local Portainer environments and their containers."""
from __future__ import annotations

import json

from portainer_client import client_from_env


def main() -> None:
    client = client_from_env()
    data = client.get_all(exclude_local=True)

    output = {}
    for endpoint_name, containers in data.items():
        output[endpoint_name] = [
            {"id": c.id, "name": c.name, "state": c.state, "image": c.image}
            for c in containers
        ]
        print(f"\n=== {endpoint_name} ({len(containers)} containers) ===")
        for c in containers:
            print(f"  [{c.state:<10}] {c.name}  ({c.image})")

    with open("environments.json", "w") as f:
        json.dump(output, f, indent=2)
    print("\nWrote environments.json")


if __name__ == "__main__":
    main()
