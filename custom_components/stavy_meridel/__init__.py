"""Experimental stavymeridel.cz integration."""
from datetime import timedelta
import logging

from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, Platform
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.storage import Store
from homeassistant.components.recorder.statistics import async_add_external_statistics
from homeassistant.components.recorder.models.statistics import StatisticMeanType
from homeassistant.util import dt as dt_util

from .api import PortalClient, ApiError, AuthError
from .const import DOMAIN, CONF_APARTMENT_CODE
from .const import METER_TYPES
from .history import history_issue, merge_history, monthly_consumption, statistic_id, statistics_rows
from .billing import monthly_costs

LOGGER = logging.getLogger(__name__)
PLATFORMS = [Platform.SENSOR, Platform.NUMBER, Platform.DATE]


class PortalCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry):
        super().__init__(hass, LOGGER, name=DOMAIN, config_entry=entry,
                         update_interval=timedelta(days=1))
        self.client = PortalClient(async_get_clientsession(hass), entry.data[CONF_USERNAME],
                                   entry.data[CONF_PASSWORD], entry.data[CONF_APARTMENT_CODE],
                                   history_years=entry.options.get("history_years", 2))
        self.tariffs = entry.options.get("tariffs", [])
        self.currency = entry.options.get("tariff_currency", hass.config.currency)
        self.last_sync = None
        self.archive = {}
        self.store = Store(hass, 1, f"{DOMAIN}.{entry.entry_id}.history")
        self.apartment_code = entry.data[CONF_APARTMENT_CODE]

    async def _async_update_data(self):
        try:
            result = await self.client.fetch(dt_util.now().date())
        except AuthError as err:
            raise ConfigEntryAuthFailed("Portal credentials rejected") from err
        except ApiError as err:
            raise UpdateFailed(str(err)) from err
        merge_history(self.archive, self.client.history)
        await self.store.async_save(self.archive)
        self.import_statistics()
        self.last_sync = dt_util.utcnow()
        return result

    def import_statistics(self):
        """Reprice cached readings without logging in or polling the portal again."""
        for key, item in self.archive.items():
            if history_issue(item):
                LOGGER.warning("Monthly statistics skipped: counter decreased outside a known reset")
                continue
            rows = statistics_rows(monthly_consumption(item), dt_util.DEFAULT_TIME_ZONE,
                                   dt_util.utcnow())
            if not rows:
                continue
            metadata = {
                "statistic_id": statistic_id(self.apartment_code, key),
                "source": DOMAIN,
                "name": (f"{METER_TYPES[item['kind']]} {item['room'] or item['serial']}"
                         f" – měsíční odečty ({self.apartment_code})"),
                "unit_of_measurement": item["unit"],
                "unit_class": "volume" if item["kind"] in (2, 4) else None,
                "has_sum": True,
                "mean_type": StatisticMeanType.NONE,
            }
            async_add_external_statistics(self.hass, metadata, rows)
            cost_rows = statistics_rows(monthly_costs(item, self.tariffs), dt_util.DEFAULT_TIME_ZONE,
                                        dt_util.utcnow())
            if cost_rows:
                cost_metadata = {**metadata,
                                 "statistic_id": statistic_id(self.apartment_code, key) + "_cost",
                                 "unit_of_measurement": self.currency,
                                 "unit_class": None,
                                 "name": metadata["name"].replace("měsíční odečty", "náklady")}
                async_add_external_statistics(self.hass, cost_metadata, cost_rows)


async def async_setup_entry(hass, entry):
    coordinator = PortalCoordinator(hass, entry)
    coordinator.archive = await coordinator.store.async_load() or {}
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


async def async_unload_entry(hass, entry):
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_options_updated(hass, entry):
    coordinator = entry.runtime_data
    if coordinator.client.history_years != entry.options.get("history_years", 2):
        await hass.config_entries.async_reload(entry.entry_id)
        return
    coordinator.tariffs = entry.options.get("tariffs", [])
    coordinator.currency = entry.options.get("tariff_currency", hass.config.currency)
    coordinator.import_statistics()
    coordinator.async_update_listeners()
