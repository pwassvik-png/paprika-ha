"""Login and retry behaviour of the API client, without HA or aiohttp installed."""
import asyncio
from pathlib import Path
import importlib.util
import sys
import types
import unittest


class ClientResponseError(Exception):
    def __init__(self, status):
        super().__init__(status)
        self.status = status
        self.message = str(status)


class FormData:
    def add_field(self, *args, **kwargs):
        pass


mods = {name: types.ModuleType(name) for name in (
    "aiohttp",
    "homeassistant",
    "homeassistant.core",
    "homeassistant.helpers",
    "homeassistant.helpers.aiohttp_client",
    "custom_components",
    "custom_components.paprika",
    "custom_components.paprika.const",
)}
mods["aiohttp"].ClientResponseError = ClientResponseError
mods["aiohttp"].ClientSession = object
mods["aiohttp"].FormData = FormData
mods["homeassistant.core"].HomeAssistant = object
mods["homeassistant.helpers.aiohttp_client"].async_get_clientsession = lambda hass: hass
const = mods["custom_components.paprika.const"]
const.API_BASE_URL = "https://paprika/"
const.LOGIN_PATH = "login/"
const.SYNC_PATH = "sync/"
const.USER_AGENT = "test"
sys.modules.update(mods)

spec = importlib.util.spec_from_file_location(
    "custom_components.paprika.api",
    Path(__file__).parents[1] / "custom_components" / "paprika" / "api.py",
)
api = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = api
spec.loader.exec_module(api)


class Response:
    def __init__(self, status, body):
        self.status = status
        self.body = body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def raise_for_status(self):
        if self.status >= 400:
            raise ClientResponseError(self.status)

    async def json(self, content_type=None):
        return self.body


class Session:
    """Answers every sync request with `sync_status`; records logins."""

    def __init__(self, sync_status=200, login_ok=True):
        self.sync_status = sync_status
        self.login_ok = login_ok
        self.logins = []
        self.requests = 0

    def post(self, url, headers=None, data=None):
        self.logins.append(dict(data))
        if not self.login_ok:
            return Response(200, {"error": {"message": "Incorrect password."}})
        return Response(200, {"result": {"token": f"t{len(self.logins)}"}})

    def request(self, method, url, headers=None, data=None):
        self.requests += 1
        return Response(self.sync_status, {"result": {"ok": True}})


def client(session):
    return api.PaprikaClient(session, api.PaprikaAuth(email="a@example.test", password="pw"))


class ApiTests(unittest.TestCase):
    def test_login_sends_only_email_and_password(self):
        session = Session()
        asyncio.run(client(session).async_fetch_status())
        self.assertEqual(session.logins, [{"email": "a@example.test", "password": "pw"}])

    def test_wrong_password_is_an_auth_error(self):
        with self.assertRaises(api.PaprikaAuthError):
            asyncio.run(client(Session(login_ok=False)).async_validate_login())

    def test_401_logs_in_again_once_then_fails(self):
        session = Session(sync_status=401)
        with self.assertRaises(api.PaprikaApiError):
            asyncio.run(client(session).async_fetch_status())
        self.assertEqual(len(session.logins), 2)
        self.assertEqual(session.requests, 2)

    def test_parallel_requests_share_one_login(self):
        session = Session()
        c = client(session)

        async def fetch_all():
            await asyncio.gather(*(c.async_fetch_status() for _ in range(7)))

        asyncio.run(fetch_all())
        self.assertEqual(len(session.logins), 1)

    def test_rejected_password_is_tried_once(self):
        session = Session(login_ok=False)
        c = client(session)

        async def fetch_all():
            return await asyncio.gather(
                *(c.async_fetch_status() for _ in range(7)), return_exceptions=True
            )

        results = asyncio.run(fetch_all())
        self.assertTrue(all(isinstance(r, api.PaprikaAuthError) for r in results))
        self.assertEqual(len(session.logins), 1)


if __name__ == "__main__":
    unittest.main()
