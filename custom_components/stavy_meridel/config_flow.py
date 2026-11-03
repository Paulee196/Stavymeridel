"""Local UI setup; credentials are only sent to stavymeridel.cz over HTTPS."""
import re
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers import selector
from homeassistant.util import dt as dt_util

from .api import PortalClient, AuthError, ApiError
from .const import DOMAIN, CONF_APARTMENT_CODE


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            user_input = dict(user_input)
            code = re.sub(r"\s+", "", user_input[CONF_APARTMENT_CODE])
            user_input[CONF_APARTMENT_CODE] = code
            if not re.fullmatch(r"\d{10}", code):
                errors[CONF_APARTMENT_CODE] = "invalid_code"
            else:
                await self.async_set_unique_id(code)
                self._abort_if_unique_id_configured()
                client = PortalClient(async_get_clientsession(self.hass),
                                      user_input[CONF_USERNAME], user_input[CONF_PASSWORD], code)
                try:
                    await client.fetch(dt_util.now().date())
                except AuthError:
                    errors["base"] = "invalid_auth"
                except ApiError:
                    errors["base"] = "cannot_connect"
                else:
                    return self.async_create_entry(title=f"Stavy měřidel {code}", data=user_input)
        return self.async_show_form(step_id="user", data_schema=vol.Schema({
            vol.Required(CONF_USERNAME): str,
            vol.Required(CONF_PASSWORD): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)),
            vol.Required(CONF_APARTMENT_CODE): str,
        }), errors=errors)

    async def async_step_reauth(self, entry_data):
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        errors = {}
        entry = self._get_reauth_entry()
        if user_input is not None:
            data = {**entry.data, **user_input}
            client = PortalClient(async_get_clientsession(self.hass), data[CONF_USERNAME],
                                  data[CONF_PASSWORD], data[CONF_APARTMENT_CODE])
            try:
                await client.fetch(dt_util.now().date())
            except AuthError:
                errors["base"] = "invalid_auth"
            except ApiError:
                errors["base"] = "cannot_connect"
            else:
                return self.async_update_reload_and_abort(entry, data_updates=user_input)
        return self.async_show_form(step_id="reauth_confirm", data_schema=vol.Schema({
            vol.Required(CONF_PASSWORD): selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD)),
        }), errors=errors)
