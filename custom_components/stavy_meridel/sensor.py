"""Readings without unverified consumption statistics or history backfill."""
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, CONF_APARTMENT_CODE, METER_TYPES


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = entry.runtime_data
    known = set()

    def discover():
        additions = []
        for key, reading in coordinator.data.items():
            if key not in known:
                known.add(key)
                additions.append(MeterSensor(coordinator, entry, key, reading))
        if additions:
            async_add_entities(additions)

    discover()
    async_add_entities([SyncSensor(coordinator, entry)])
    entry.async_on_unload(coordinator.async_add_listener(discover))


class MeterSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry, key, reading):
        super().__init__(coordinator)
        self.key = key
        code = entry.data[CONF_APARTMENT_CODE]
        self._attr_unique_id = f"{code}_{key}"
        self._attr_name = f"{METER_TYPES[reading.kind]} {reading.room or reading.serial}"
        self._attr_native_unit_of_measurement = reading.unit
        self._attr_icon = "mdi:water" if reading.kind in (2, 4) else "mdi:radiator"
        # Deliberately no state_class: monthly publication dates are not reading timestamps.
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, code)},
                                            name=f"Odečty bytu {code}",
                                            manufacturer="stavymeridel.cz")

    @property
    def available(self):
        reading = self.coordinator.data.get(self.key)
        return super().available and reading is not None and reading.value is not None

    @property
    def native_value(self):
        reading = self.coordinator.data.get(self.key)
        return reading.value if reading else None

    @property
    def extra_state_attributes(self):
        reading = self.coordinator.data.get(self.key)
        if reading is None:
            return {}
        return {"serial_number": reading.serial, "room": reading.room,
                "reading_period": reading.period, "source": "stavymeridel.cz"}


class SyncSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True
    _attr_name = "Poslední úspěšná synchronizace"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, entry):
        super().__init__(coordinator)
        code = entry.data[CONF_APARTMENT_CODE]
        self._attr_unique_id = f"{code}_last_sync"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, code)})

    @property
    def native_value(self):
        return self.coordinator.last_sync
