"""Visible calendar control for the effective month of subsequent price edits."""
from homeassistant.components.date import DateEntity
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .billing import editor_date
from .const import DOMAIN, CONF_APARTMENT_CODE


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([PriceDateControl(entry)])


class PriceDateControl(CoordinatorEntity, DateEntity):
    _attr_has_entity_name = True
    _attr_name = "1. Platnost nově zadané ceny od"
    _attr_icon = "mdi:calendar-edit"

    def __init__(self, entry):
        super().__init__(entry.runtime_data)
        self.entry = entry
        code = entry.data[CONF_APARTMENT_CODE]
        self._attr_unique_id = f"{code}_price_effective_from"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, code)})

    @property
    def available(self):
        return True

    @property
    def native_value(self):
        return editor_date(self.entry.options, dt_util.now().date())

    async def async_set_value(self, value):
        if value.day != 1:
            raise HomeAssistantError("Vyberte první den měsíce; odečty jsou měsíční.")
        self.hass.config_entries.async_update_entry(
            self.entry, options={**self.entry.options, "price_editor_date": value.isoformat()})
        self.async_write_ha_state()
