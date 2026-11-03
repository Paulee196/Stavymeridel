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
from .const import METER_TYPES
from .billing import set_tariff
from homeassistant.core import callback


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return OptionsFlow()

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


class OptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        return self.async_show_menu(step_id="init", menu_options=["price", "history"])

    async def async_step_price(self, user_input=None):
        errors = {}
        currency = self.config_entry.options.get("tariff_currency", self.hass.config.currency)
        tariffs = self.config_entry.options.get("tariffs", [])
        if user_input is not None:
            from datetime import date
            start = date.fromisoformat(user_input["effective_from"])
            if start.day != 1:
                errors["effective_from"] = "month_start_required"
            else:
                options = dict(self.config_entry.options)
                try:
                    options["tariffs"] = set_tariff(tariffs, int(user_input["meter_type"]),
                                                   start.strftime("%Y-%m"), float(user_input["price"]))
                except ValueError:
                    errors["price"] = "invalid_price"
                else:
                    options["tariff_currency"] = currency
                    return self.async_create_entry(title="", data=options)
        summary = "\n".join(
            f"{METER_TYPES[t['kind']]}: {t['from']} → {t['price']:g} {currency}/"
            f"{'dílek (odhad)' if t['kind'] == 19 else 'm³'}" for t in tariffs
        ) or "—"
        return self.async_show_form(step_id="price", data_schema=vol.Schema({
            vol.Required("meter_type", default="4"): selector.SelectSelector(
                selector.SelectSelectorConfig(options=[
                    {"value": "4", "label": "Studená voda – za m³"},
                    {"value": "2", "label": "Teplá voda včetně ohřevu – za m³"},
                    {"value": "19", "label": "Topení – odhad za dílek"},
                ])),
            vol.Required("effective_from", default=dt_util.now().date().replace(day=1).isoformat()):
                selector.DateSelector(),
            vol.Required("price"): selector.NumberSelector(selector.NumberSelectorConfig(
                min=0, max=1000000, step=0.01, mode=selector.NumberSelectorMode.BOX,
                unit_of_measurement=f"{currency}/jednotku")),
        }), errors=errors, description_placeholders={"tariffs": summary, "currency": currency})

    async def async_step_history(self, user_input=None):
        if user_input is not None:
            options = dict(self.config_entry.options)
            options["history_years"] = int(user_input["history_years"])
            return self.async_create_entry(title="", data=options)
        return self.async_show_form(step_id="history", data_schema=vol.Schema({
            vol.Required("history_years", default=self.config_entry.options.get("history_years", 2)):
                selector.NumberSelector(selector.NumberSelectorConfig(
                    min=1, max=5, step=1, mode=selector.NumberSelectorMode.BOX)),
        }))
