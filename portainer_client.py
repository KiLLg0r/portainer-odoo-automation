"""Portainer API client: auth, list environments/containers, control + exec."""
from __future__ import annotations

import os
import json
import time
from dataclasses import dataclass
from typing import Iterable

import requests
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Container:
    id: str
    name: str
    state: str  # "running", "exited", etc.
    image: str
    endpoint_id: int
    endpoint_name: str


class PortainerClient:
    def __init__(self, base_url: str, username: str | None = None,
                 password: str | None = None, api_key: str | None = None,
                 verify_ssl: bool = True, timeout: int = 30,
                 basic_auth: tuple[str, str] | None = None):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.verify = verify_ssl
        # nginx in front of Portainer enforces a Referer check on write methods.
        self.session.headers["Referer"] = self.base_url + "/"
        if basic_auth:
            self.session.auth = basic_auth

        # Auth strategy:
        #   - If basic_auth is set (nginx in front of Portainer), we must NOT
        #     send X-API-Key or Authorization: Bearer, because Portainer
        #     rejects any request that has X-API-Key + Authorization together,
        #     and the basic-auth Authorization header is always present.
        #     Instead we log in with username/password to get a JWT and pass
        #     it in the `portainer_api_key` cookie (same mechanism the UI uses).
        #   - Without basic_auth, X-API-Key or Bearer JWT both work.
        if basic_auth:
            if not (username and password):
                raise ValueError(
                    "Basic auth is set, so Portainer username+password are "
                    "required (API key alone cannot be used behind nginx "
                    "basic auth)."
                )
            jwt = self._login(username, password)
            self.session.cookies.set("portainer_api_key", jwt)
        elif api_key:
            self.session.headers["X-API-Key"] = api_key
        elif username and password:
            token = self._login(username, password)
            self.session.headers["Authorization"] = f"Bearer {token}"
        else:
            raise ValueError("Provide api_key or username+password")

        # gorilla/csrf protection: fetch the root page once to obtain the
        # X-Csrf-Token header + _gorilla_csrf cookie, then echo the token
        # back on write requests.
        self._prime_csrf()

    def _prime_csrf(self) -> None:
        r = self.session.get(self.base_url + "/", timeout=self.timeout)
        token = r.headers.get("X-Csrf-Token") or r.headers.get("X-CSRF-Token")
        if token:
            self.session.headers["X-CSRF-Token"] = token

    def _login(self, username: str, password: str) -> str:
        r = self.session.post(
            f"{self.base_url}/api/auth",
            json={"username": username, "password": password},
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json()["jwt"]

    def list_endpoints(self, exclude_local: bool = True) -> list[dict]:
        r = self.session.get(f"{self.base_url}/api/endpoints", timeout=self.timeout)
        r.raise_for_status()
        endpoints = r.json()
        if exclude_local:
            # Type 1 = Docker local socket. Also filter by name == "local" as a safety net.
            endpoints = [
                e for e in endpoints
                if e.get("Type") != 1 and e.get("Name", "").lower() != "local"
            ]
        return endpoints

    def list_containers(self, endpoint_id: int, endpoint_name: str = "",
                        all_containers: bool = True) -> list[Container]:
        r = self.session.get(
            f"{self.base_url}/api/endpoints/{endpoint_id}/docker/containers/json",
            params={"all": str(all_containers).lower()},
            timeout=self.timeout,
        )
        r.raise_for_status()
        out = []
        for c in r.json():
            names = c.get("Names") or []
            name = names[0].lstrip("/") if names else c["Id"][:12]
            out.append(Container(
                id=c["Id"],
                name=name,
                state=c.get("State", ""),
                image=c.get("Image", ""),
                endpoint_id=endpoint_id,
                endpoint_name=endpoint_name,
            ))
        return out

    def get_all(self, exclude_local: bool = True) -> dict[str, list[Container]]:
        """Returns {endpoint_name: [Container, ...]} for non-local endpoints."""
        result: dict[str, list[Container]] = {}
        for ep in self.list_endpoints(exclude_local=exclude_local):
            result[ep["Name"]] = self.list_containers(ep["Id"], ep["Name"])
        return result

    # --- container control ---

    def _container_action(self, c: Container, action: str) -> None:
        r = self.session.post(
            f"{self.base_url}/api/endpoints/{c.endpoint_id}"
            f"/docker/containers/{c.id}/{action}",
            timeout=self.timeout,
        )
        # 204 success, 304 already in target state
        if r.status_code not in (204, 304):
            r.raise_for_status()

    def start(self, c: Container) -> None:
        self._container_action(c, "start")

    def stop(self, c: Container) -> None:
        self._container_action(c, "stop")

    def restart(self, c: Container) -> None:
        self._container_action(c, "restart")

    # --- exec ---

    def exec_run(self, c: Container, cmd: list[str],
                 user: str | None = None) -> tuple[int, str]:
        """Run cmd in container. Returns (exit_code, combined_output)."""
        payload = {
            "AttachStdout": True,
            "AttachStderr": True,
            "Tty": False,
            "Cmd": cmd,
        }
        if user:
            payload["User"] = user

        r = self.session.post(
            f"{self.base_url}/api/endpoints/{c.endpoint_id}"
            f"/docker/containers/{c.id}/exec",
            json=payload,
            timeout=self.timeout,
        )
        r.raise_for_status()
        exec_id = r.json()["Id"]

        r = self.session.post(
            f"{self.base_url}/api/endpoints/{c.endpoint_id}"
            f"/docker/exec/{exec_id}/start",
            json={"Detach": False, "Tty": False},
            timeout=None,
            stream=True,
        )
        r.raise_for_status()
        output = r.content.decode("utf-8", errors="replace")

        r = self.session.get(
            f"{self.base_url}/api/endpoints/{c.endpoint_id}"
            f"/docker/exec/{exec_id}/json",
            timeout=self.timeout,
        )
        r.raise_for_status()
        return r.json().get("ExitCode") or 0, output

    def wait_running(self, c: Container, timeout: int = 60,
                     poll: float = 2.0) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            current = self.list_containers(c.endpoint_id, c.endpoint_name)
            for cc in current:
                if cc.id == c.id and cc.state == "running":
                    return True
            time.sleep(poll)
        return False


def client_from_env() -> PortainerClient:
    """Build a client from PORTAINER_URL + (PORTAINER_API_KEY | USER/PASSWORD)."""
    url = os.environ["PORTAINER_URL"]
    api_key = os.environ.get("PORTAINER_API_KEY")
    user = os.environ.get("PORTAINER_USERNAME")
    pw = os.environ.get("PORTAINER_PASSWORD")
    verify = os.environ.get("PORTAINER_VERIFY_SSL", "true").lower() != "false"

    ba_user = os.environ.get("PORTAINER_BASIC_AUTH_USER")
    ba_pw = os.environ.get("PORTAINER_BASIC_AUTH_PASSWORD")
    basic_auth = (ba_user, ba_pw) if ba_user and ba_pw else None

    return PortainerClient(url, username=user, password=pw,
                           api_key=api_key, verify_ssl=verify,
                           basic_auth=basic_auth)
