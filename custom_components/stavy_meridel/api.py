"""Read-only HTTPS client. Never logs credentials or server response bodies."""
import asyncio
from base64 import b64encode
from datetime import date
import aiohttp

from .const import BASE_URL, METER_TYPES
from .parser import SchemaError, parse_dashboard
from .history import parse_history


class ApiError(Exception):
    """Connection, access or response error."""


class AuthError(ApiError):
    """Credentials rejected."""


class PortalClient:
    def __init__(self, session, username, password, apartment_code):
        self.session = session
        self.username = username
        self.password = password
        self.apartment_code = apartment_code
        self.token = None
        self.apartment_id = None
        self.history = {}

    async def _request(self, path, *, login=False, params=None):
        headers = {"Accept": "application/json"}
        if login:
            if ":" in self.username:
                raise AuthError("Invalid login name")
            try:
                credentials = f"{self.username}:{self.password}".encode("latin1")
                headers["Authorization"] = "Basic " + b64encode(credentials).decode("ascii")
            except UnicodeEncodeError as err:
                raise AuthError("Unsupported login characters") from err
        else:
            headers.update({"Authorization": f"Bearer {self.token}", "roleId": "1"})
        try:
            async with self.session.get(BASE_URL + path, headers=headers, params=params,
                                        timeout=aiohttp.ClientTimeout(total=30),
                                        allow_redirects=False) as response:
                if response.status == 401:
                    raise AuthError("Authentication rejected")
                if response.status != 200:
                    raise ApiError(f"Portal HTTP status {response.status}")
                try:
                    data = await response.json()
                except (ValueError, aiohttp.ContentTypeError) as err:
                    raise ApiError("Expected JSON; portal may require browser verification") from err
                if not isinstance(data, dict):
                    raise ApiError("Unexpected response format")
                return data
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise ApiError("Cannot connect to portal") from err

    async def login(self):
        self.token = None
        data = await self._request("login", login=True)
        if not isinstance(data.get("token"), str) or not data["token"]:
            raise ApiError("Login did not return a token")
        self.token = data["token"]

    async def get(self, path, params=None):
        if self.token is None:
            await self.login()
        try:
            return await self._request(path, params=params)
        except AuthError:
            await self.login()
            return await self._request(path, params=params)

    async def fetch(self, today=None):
        today = today or date.today()
        if self.apartment_id is None:
            apartment = await self.get("apartments/byCode", {"code": self.apartment_code})
            apartment_id = apartment.get("id")
            if isinstance(apartment_id, bool) or not isinstance(apartment_id, int):
                raise ApiError("Apartment ID missing")
            self.apartment_id = apartment_id
        readings = {}
        history = {}
        for kind in METER_TYPES:
            params = {"meterTypeID": kind, "year1": today.year - 1, "year2": today.year}
            data = await self.get(f"apartment/{self.apartment_id}/dashboard", params)
            try:
                parsed = parse_dashboard(data, kind, today)
                if kind == 19 and not parsed:
                    params["meterTypeID"] = -19
                    data = await self.get(f"apartment/{self.apartment_id}/dashboard", params)
                    parsed = parse_dashboard(data, 19, today)
                history.update(parse_history(data, kind, today))
            except SchemaError as err:
                raise ApiError(f"Unrecognized meter table (type {kind}): {err}") from err
            for reading in parsed:
                readings[f"{kind}_{reading.serial}"] = reading
        if not readings:
            raise ApiError("No meters returned")
        self.history = history
        return readings
