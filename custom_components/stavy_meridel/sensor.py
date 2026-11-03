"""Readings without unverified consumption statistics or history backfill."""
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.helpers.entity import DeviceInfo, EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, CONF_APARTMENT_CODE, METER_TYPES
from .history import history_issue, monthly_consumption, statistic_id
from homeassistant.util import dt as dt_util


async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = entry.runtime_data
    known = set()

    def discover():
        additions = []
        for key, reading in coordinator.data.items():
            if key not in known:
                known.add(key)
                additions.append(MeterSensor(coordinator, entry, key, reading))
                additions.extend(ConsumptionSensor(coordinator, entry, key, reading, period)
                                 for period in ("month", "year"))
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
        self.apartment_code = entry.data[CONF_APARTMENT_CODE]
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
                "reading_period": reading.period, "source": "stavymeridel.cz",
                "monthly_statistic_id": statistic_id(self.apartment_code, self.key)}


class ConsumptionSensor(MeterSensor):
    """Convenient period totals; external statistics carry the correct monthly history."""
    def __init__(self, coordinator, entry, key, reading, period):
        super().__init__(coordinator, entry, key, reading)
        self.period = period
        self._attr_unique_id += f"_{period}"
        suffix = "tento měsíc" if period == "month" else "tento rok"
        self._attr_name += f" – {suffix}"

    @property
    def available(self):
        return self.coordinator.last_update_success and self.native_value is not None

    @property
    def native_value(self):
        amounts = monthly_consumption(self.coordinator.archive.get(self.key, {"months": {}}))
        now = dt_util.now()
        if self.period == "month":
            return amounts.get(now.strftime("%Y-%m"))
        values = [value for period, value in amounts.items() if period.startswith(f"{now.year}-")]
        return round(sum(values), 6) if values else None

    @property
    def extra_state_attributes(self):
        item = self.coordinator.archive.get(self.key, {"months": {}})
        amounts = monthly_consumption(item)
        now = dt_util.now()
        year = {p: v for p, v in amounts.items() if p.startswith(f"{now.year}-")}
        return {"monthly_statistic_id": statistic_id(self.apartment_code, self.key),
                "known_months_this_year": len(year),
                "year_incomplete": len(year) < now.month,
                "current_month_provisional": True,
                "history_issue": history_issue(item)}


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
