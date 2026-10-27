"""Asynchronous Paprika API client."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
import gzip
import json
from typing import Any, Dict, List, Optional

from aiohttp import ClientResponseError, ClientSession, FormData

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import API_BASE_URL, LOGIN_PATH, SYNC_PATH, USER_AGENT


class PaprikaApiError(Exception):
    """General Paprika API error."""


class PaprikaAuthError(PaprikaApiError):
    """Paprika rejected the email or password."""


@dataclass
class PaprikaAuth:
    """Authentication context for Paprika."""

    email: str
    password: str


class PaprikaClient:
    """Client used to interact with Paprika sync endpoints."""

    def __init__(self, hass: HomeAssistant, auth: PaprikaAuth) -> None:
        """Initialise Paprika client."""
        self._session: ClientSession = async_get_clientsession(hass)
        self._auth = auth
        self._token: Optional[str] = None
        # The coordinator fetches several lists at once; they share one login,
        # and a rejected password is not tried again until the entry reloads.
        self._login_lock = asyncio.Lock()
        self._rejected: Optional[PaprikaAuthError] = None

    async def _ensure_token(self, *, force: bool = False) -> None:
        """Ensure a bearer token is available."""
        if self._token and not force:
            return
        stale = self._token
        async with self._login_lock:
            if self._rejected:
                raise self._rejected
            # Another request may have logged in while this one waited.
            if self._token and self._token != stale:
                return
            try:
                await self._async_login()
            except PaprikaAuthError as err:
                self._rejected = err
                raise

    async def _async_login(self) -> None:
        """Perform login to obtain bearer token."""
        url = f"{API_BASE_URL}{LOGIN_PATH}"
        headers = {
            "User-Agent": USER_AGENT,
            "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
            "Accept": "*/*",
        }
        # The apps also send an App Store receipt, but the API does not need it.
        payload = {"email": self._auth.email, "password": self._auth.password}

        try:
            async with asyncio.timeout(20):
                async with self._session.post(url, headers=headers, data=payload) as resp:
                    resp.raise_for_status()
                    payload = await resp.json(content_type=None)
        except ClientResponseError as err:
            if err.status in (401, 403):
                raise PaprikaAuthError("Paprika godtog inte inloggningen") from err
            raise PaprikaApiError(
                f"Paprika login misslyckades ({err.status})"
            ) from err
        except asyncio.TimeoutError as err:
            raise PaprikaApiError("Paprika login timeout") from err
        except Exception as err:  # noqa: BLE001
            raise PaprikaApiError("Paprika loginfel") from err

        result = payload.get("result") or {}
        token = result.get("token")
        if not token:
            message = payload.get("error", {}).get("message", "Okänt svar")
            raise PaprikaAuthError(f"Paprika login svarade utan token: {message}")
        self._token = token

    async def _request(
        self,
        path: str,
        *,
        method: str = "GET",
        data: Any = None,
        gzip_json: Any = None,
        retry_auth: bool = True,
    ) -> Any:
        """Perform a request against Paprika and return JSON.

        `gzip_json` is sent the way the Paprika apps upload changes: as a
        gzipped JSON file in the multipart field `data`.
        """
        await self._ensure_token()
        if gzip_json is not None:
            form = FormData()
            form.add_field(
                "data",
                gzip.compress(json.dumps(gzip_json).encode()),
                filename="data",
                content_type="application/octet-stream",
            )
            data = form
        url = f"{API_BASE_URL}{SYNC_PATH}{path}"
        headers = {
            "User-Agent": USER_AGENT,
            "Authorization": f"Bearer {self._token}",
        }

        expired = False
        try:
            async with asyncio.timeout(20):
                async with self._session.request(
                    method,
                    url,
                    headers=headers,
                    data=data,
                ) as resp:
                    if resp.status == 401 and retry_auth:
                        expired = True
                    else:
                        resp.raise_for_status()
                        payload = await resp.json(content_type=None)
        except ClientResponseError as err:
            raise PaprikaApiError(
                f"Paprika request failed ({err.status}): {err.message}"
            ) from err
        except asyncio.TimeoutError as err:
            raise PaprikaApiError("Paprika request timed out") from err
        except Exception as err:  # noqa: BLE001
            raise PaprikaApiError("Paprika request error") from err

        if expired:
            # Log in again once. A second 401 raises instead of looping, which
            # would otherwise hammer the API until it answers 429.
            await self._ensure_token(force=True)
            return await self._request(
                path,
                method=method,
                data=None if gzip_json is not None else data,
                gzip_json=gzip_json,
                retry_auth=False,
            )
        return payload.get("result", payload)

    async def async_validate_login(self) -> None:
        """Log in now, so the config flow can report wrong credentials."""
        await self._ensure_token(force=True)

    async def async_fetch_status(self) -> Dict[str, Any]:
        """Fetch overall status counts."""
        return await self._request("status/")

    async def async_fetch_meals(self) -> List[Dict[str, Any]]:
        """Fetch meal plan entries."""
        return await self._request("meals/")

    async def async_fetch_menu_items(self) -> List[Dict[str, Any]]:
        """Fetch menu items (long term planning)."""
        return await self._request("menuitems/")

    async def async_fetch_groceries(self) -> List[Dict[str, Any]]:
        """Fetch grocery list entries."""
        return await self._request("groceries/")

    async def async_fetch_meal_types(self) -> List[Dict[str, Any]]:
        """Fetch meal types metadata."""
        return await self._request("mealtypes/")

    async def async_fetch_recipes(self) -> List[Dict[str, Any]]:
        """Fetch the recipe index: only `uid` and `hash` per recipe."""
        return await self._request("recipes/")

    async def async_fetch_recipe(self, uid: str) -> Dict[str, Any]:
        """Fetch one full recipe."""
        return await self._request(f"recipe/{uid}/")

    async def async_fetch_categories(self) -> List[Dict[str, Any]]:
        """Fetch recipe categories."""
        return await self._request("categories/")

    async def async_save_recipe(self, recipe: Dict[str, Any]) -> None:
        """Create or update one recipe (a single object, not an array)."""
        await self._request(
            f"recipe/{recipe['uid']}/", method="POST", gzip_json=recipe
        )
        await self._request("notify/", method="POST")

    async def async_fetch_pantry(self) -> List[Dict[str, Any]]:
        """Fetch pantry (köksskåp) items."""
        return await self._request("pantry/")

    async def async_save_pantry(self, items: List[Dict[str, Any]]) -> None:
        """Create, update or delete (`deleted: True`) pantry items and sync."""
        await self._request("pantry/", method="POST", gzip_json=items)
        await self._request("notify/", method="POST")

    async def async_save_groceries(self, groceries: List[Dict[str, Any]]) -> None:
        """Create or update grocery items and tell the apps to sync."""
        await self._request("groceries/", method="POST", gzip_json=groceries)
        await self._request("notify/", method="POST")
