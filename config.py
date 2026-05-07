"""Read tunable defaults from environment variables.

All values default to the project's original hardcoded values, so
unsetting everything reproduces the pre-config behavior."""
from __future__ import annotations

import os

from dotenv import load_dotenv


load_dotenv()


def _str(name: str, default: str) -> str:
    return os.environ.get(name, default)


def _int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _csv(name: str, default: list[str]) -> list[str]:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return list(default)
    return [v.strip() for v in raw.split(",") if v.strip()]


# --- Odoo ---
ODOO_CONF_PATH: str = _str("ODOO_CONF_PATH", "/etc/odoo/odoo.conf")
ODOO_HTTP_PORT: str = _str("ODOO_HTTP_PORT", "9999")
ODOO_DEFAULT_MODULES: list[str] = _csv("ODOO_DEFAULT_MODULES", ["dp_base"])

# --- psql / DB container conventions ---
DB_CONTAINER_SUFFIX: str = _str("DB_CONTAINER_SUFFIX", "_db")
PSQL_USER_TEMPLATE: str = _str("PSQL_USER_TEMPLATE", "{name}")
PSQL_DB_TEMPLATE: str = _str("PSQL_DB_TEMPLATE", "{name}")

# --- Runner ---
WAIT_RUNNING_TIMEOUT: int = _int("WAIT_RUNNING_TIMEOUT", 120)
PER_ENV_WORKERS_DEFAULT: int = _int("PER_ENV_WORKERS_DEFAULT", 10)
