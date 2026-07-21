from __future__ import annotations

import json
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class AuthError(Exception):
    """A safe, user-facing authentication error."""


class SupabaseAuth:
    def __init__(self, url: str, anon_key: str):
        self.url = url.rstrip("/")
        self.anon_key = anon_key.strip()

    @property
    def configured(self) -> bool:
        return bool(self.url and self.anon_key)

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self.configured:
            raise AuthError("Die Anmeldung ist noch nicht vollständig konfiguriert.")
        request = Request(
            f"{self.url}/auth/v1/{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"apikey": self.anon_key, "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=15) as response:
                return json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            try:
                detail = json.loads(exc.read().decode("utf-8"))
                message = detail.get("msg") or detail.get("message") or detail.get("error_description")
            except (json.JSONDecodeError, UnicodeDecodeError):
                message = None
            if exc.code in (400, 401):
                raise AuthError("E-Mail-Adresse oder Passwort ist falsch.") from exc
            raise AuthError(message or "Die Anmeldung ist momentan nicht verfügbar.") from exc
        except (URLError, TimeoutError) as exc:
            raise AuthError("Der Anmeldedienst ist momentan nicht erreichbar.") from exc

    def sign_in(self, email: str, password: str) -> dict[str, Any]:
        return self._post("token?grant_type=password", {"email": email, "password": password})

    def refresh(self, refresh_token: str) -> dict[str, Any]:
        return self._post("token?grant_type=refresh_token", {"refresh_token": refresh_token})
