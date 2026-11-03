"""Experimental stavymeridel.cz integration."""
from datetime import timedelta
import logging

from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, Platform
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import PortalClient, ApiError, AuthError
from .const import DOMAIN, CONF_APARTMENT_CODE

LOGGER = logging.getLogger(__name__)


class PortalCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry):
        super().__init__(hass, LOGGER, name=DOMAIN, config_entry=entry,
                         update_interval=timedelta(days=1))
        self.client = PortalClient(async_get_clientsession(hass), entry.data[CONF_USERNAME],
                                   entry.data[CONF_PASSWORD], entry.data[CONF_APARTMENT_CODE])
        self.last_sync = None

    async def _async_update_data(self):
        try:
            result = await self.client.fetch(dt_util.now().date())
        except AuthError as err:
            raise ConfigEntryAuthFailed("Portal credentials rejected") from err
        except ApiError as err:
            raise UpdateFailed(str(err)) from err
        self.last_sync = dt_util.utcnow()
        return result


async def async_setup_entry(hass, entry):
    coordinator = PortalCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, [Platform.SENSOR])
    return True


async def async_unload_entry(hass, entry):
    return await hass.config_entries.async_unload_platforms(entry, [Platform.SENSOR])
