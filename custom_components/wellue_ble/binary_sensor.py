"""Binary sensor entities.

A binary sensor is on or off. Its "device class" decides how Home Assistant
shows those two states, e.g. Detected/Clear or Charging/Not charging.

Two kinds, like sensor.py:

- **Readings**, from the latest SensorReading: finger present, charging and
  reading valid.
- **Settings**, from the device's DeviceInfo: whether the SpO2 alert and the
  heart rate alert are switched on. Diagnostic, and read-only for now.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import override

from wellue_ble import DeviceInfo as WellueDeviceInfo, SensorReading

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .coordinator import WellueConfigEntry
from .entity import WellueCheckmeO2Entity

# No limit on parallel updates; see the same line in sensor.py.
PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class WellueReadingBinarySensorEntityDescription(BinarySensorEntityDescription):
    """A binary sensor whose value comes from the latest SensorReading."""

    # Takes a SensorReading and returns True (on), False (off), or None (no
    # value, which makes the binary sensor Unavailable).
    value_fn: Callable[[SensorReading], bool | None]


@dataclass(frozen=True, kw_only=True)
class WellueSettingBinarySensorEntityDescription(BinarySensorEntityDescription):
    """A binary sensor whose value comes from the device's settings."""

    # Takes a DeviceInfo and returns True (on), False (off), or None.
    value_fn: Callable[[WellueDeviceInfo], bool | None]


def _is_charging(reading: SensorReading) -> bool | None:
    """Return whether the device is charging, or None if the state is unknown.

    On only while actively charging; off once fully charged, even if it's
    still on its dock (same as the ESPHome setup).

    Careful: ChargingState.NOT_CHARGING is 0, which Python treats as False.
    So test "is None" explicitly, never "if reading.charging_state:".
    """
    if reading.charging_state is None:
        return None
    return reading.is_charging


READING_BINARY_SENSOR_DESCRIPTIONS: tuple[
    WellueReadingBinarySensorEntityDescription, ...
] = (
    WellueReadingBinarySensorEntityDescription(
        key="finger_present",
        translation_key="finger_present",
        # OCCUPANCY shows the states as Detected / Clear.
        device_class=BinarySensorDeviceClass.OCCUPANCY,
        # The library ignores the finger flag while charging, because the
        # firmware falsely reports a finger while docked.
        value_fn=lambda reading: reading.finger_detected,
    ),
    WellueReadingBinarySensorEntityDescription(
        key="charging",
        # No translation_key: Home Assistant names it "Charging" from the
        # device class, and shows the states as Charging / Not charging.
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        value_fn=_is_charging,
    ),
    WellueReadingBinarySensorEntityDescription(
        key="reading_valid",
        translation_key="reading_valid",
        # True when the health values are real measurements: a finger is
        # present and SpO2 and heart rate are within believable ranges.
        value_fn=lambda reading: reading.reading_is_valid,
    ),
)

# No device class, so these show as On / Off.
SETTING_BINARY_SENSOR_DESCRIPTIONS: tuple[
    WellueSettingBinarySensorEntityDescription, ...
] = (
    WellueSettingBinarySensorEntityDescription(
        key="oxygen_alert",
        translation_key="oxygen_alert",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda settings: settings.oxygen_alert_enabled,
    ),
    WellueSettingBinarySensorEntityDescription(
        key="heart_rate_alert",
        translation_key="heart_rate_alert",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda settings: settings.heart_rate_alert_enabled,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: WellueConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Create the binary sensors. Home Assistant calls this during setup."""
    coordinator = entry.runtime_data
    async_add_entities(
        WellueCheckmeO2ReadingBinarySensor(coordinator, description)
        for description in READING_BINARY_SENSOR_DESCRIPTIONS
    )
    async_add_entities(
        WellueCheckmeO2SettingBinarySensor(coordinator, description)
        for description in SETTING_BINARY_SENSOR_DESCRIPTIONS
    )


class WellueCheckmeO2ReadingBinarySensor(WellueCheckmeO2Entity, BinarySensorEntity):
    """A binary sensor showing one value from the latest reading."""

    entity_description: WellueReadingBinarySensorEntityDescription

    @property
    @override
    def is_on(self) -> bool | None:
        """Return True for on, False for off, from the latest reading."""
        reading = self.coordinator.data
        # No reading yet, or monitoring is off.
        if reading is None:
            return None
        return self.entity_description.value_fn(reading)

    @property
    @override
    def available(self) -> bool:
        """Unavailable when the last update failed, or the value is missing."""
        return super().available and self.is_on is not None


class WellueCheckmeO2SettingBinarySensor(WellueCheckmeO2Entity, BinarySensorEntity):
    """A diagnostic binary sensor showing one of the device's settings."""

    entity_description: WellueSettingBinarySensorEntityDescription

    @property
    @override
    def is_on(self) -> bool | None:
        """Return the setting's value, as last fetched from the device."""
        settings = self.coordinator.wellue_device_info
        # Not fetched yet, or monitoring is off.
        if settings is None:
            return None
        return self.entity_description.value_fn(settings)

    @property
    @override
    def available(self) -> bool:
        """Unavailable when the last update failed, or the value is missing."""
        return super().available and self.is_on is not None
