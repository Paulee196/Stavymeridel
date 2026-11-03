"""Visible price controls at the top of the meter device page."""
from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .billing import editor_date, price_control_options, price_for_month
from .const import DOMAIN, CONF_APARTMENT_CODE


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([PriceControl(entry, kind) for kind in (4, 2, 19)])


class PriceControl(CoordinatorEntity, NumberEntity):
    _attr_has_entity_name = True
    _attr_mode = NumberMode.BOX
    _attr_native_min_value = 0
    _attr_native_max_value = 1000000
    _attr_native_step = 0.01
    _attr_icon = "mdi:cash-edit"

    def __init__(self, entry, kind):
        super().__init__(entry.runtime_data)
        self.entry = entry
        self.kind = kind
        self._attr_name = {4: "2. Cena studené vody", 2: "3. Cena teplé vody včetně ohřevu",
                           19: "4. Cena topení za dílek (odhad)"}[kind]
        code = entry.data[CONF_APARTMENT_CODE]
        self._attr_unique_id = f"{code}_price_{kind}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, code)})

    @property
    def available(self):
        # Price editing must remain available even during a portal outage.
        return True

    @property
    def native_unit_of_measurement(self):
        return f"{self.coordinator.currency}/{'dílek' if self.kind == 19 else 'm³'}"

    @property
    def native_value(self):
        period = editor_date(self.entry.options, dt_util.now().date()).strftime("%Y-%m")
        return price_for_month(self.entry.options.get("tariffs", []), self.kind, period)

    @property
    def extra_state_attributes(self):
        return {"valid_from": editor_date(self.entry.options, dt_util.now().date()).isoformat(),
                "price_is_estimate": self.kind == 19}

    async def async_set_native_value(self, value):
        try:
            options = price_control_options(self.entry.options, self.kind, value,
                                            dt_util.now().date(), self.hass.config.currency)
        except ValueError as err:
            raise HomeAssistantError("Zadejte nezápornou konečnou cenu.") from err
        self.hass.config_entries.async_update_entry(self.entry, options=options)
        self.async_write_ha_state()
